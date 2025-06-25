from datetime import datetime
from enum import IntEnum
from typing import Annotated, List
from fastapi import APIRouter, Depends, Form, Query, status, Response
from sqlalchemy.orm.session import Session
from fastapi.encoders import jsonable_encoder
from shapely import Point
from sqlalchemy import func
from geoalchemy2 import Geography

from app.api.bearer import bearer_executive, bearer_operator, bearer_vendor
from app.src import schemas, exceptions
from app.src.enums import OrderIn
from app.src.constants import EPSG_4326
from app.src.db import sessionMaker, Landmark, BusStop
from app.src.functions import (
    enumStr,
    toWKTgeometry,
    isSRID4326,
    getExecutiveRole,
    getExecutiveToken,
    getRequestInfo,
    logExecutiveEvent,
    makeExceptionResponses,
    getOperatorToken,
    getVendorToken,
)

route_executive = APIRouter()
route_operator = APIRouter()
route_vendor = APIRouter()


## Schemas
class OrderBy(IntEnum):
    id = 1
    landmark_id = 2
    location = 3
    created_on = 4
    updated_on = 5


class BusStopQueryParams:
    def __init__(
        self,
        id: int | None = Query(default=None),
        id_ge: int | None = Query(default=None),
        id_le: int | None = Query(default=None),
        id_list: List[int | None] = Query(
            default=None,
        ),
        name: str | None = Query(default=None),
        landmark_id: int | None = Query(default=None),
        location: str | None = Query(
            default=None, description="Accepts only SRID 4326 (WGS84)"
        ),
        created_on: datetime | None = Query(default=None),
        created_on_ge: datetime | None = Query(default=None),
        created_on_le: datetime | None = Query(default=None),
        updated_on: datetime | None = Query(default=None),
        updated_on_ge: datetime | None = Query(default=None),
        updated_on_le: datetime | None = Query(default=None),
        offset: int = Query(default=0, ge=0),
        limit: int = Query(default=20, gt=0, le=100),
        order_by: OrderBy = Query(default=OrderBy.id, description=enumStr(OrderBy)),
        order_in: OrderIn = Query(default=OrderIn.DESC, description=enumStr(OrderIn)),
    ):
        self.id = id
        self.id_ge = id_ge
        self.id_le = id_le
        self.id_list = id_list
        self.name = name
        self.landmark_id = landmark_id
        self.location = location
        self.created_on = created_on
        self.created_on_ge = created_on_ge
        self.created_on_le = created_on_le
        self.updated_on = updated_on
        self.updated_on_ge = updated_on_ge
        self.updated_on_le = updated_on_le
        self.offset = offset
        self.limit = limit
        self.order_by = order_by
        self.order_in = order_in


## Function
def queryBusStops(session: Session, qParam: BusStopQueryParams) -> List[BusStop]:
    query = session.query(BusStop)
    if qParam.id is not None:
        query = query.filter(BusStop.id == qParam.id)
    if qParam.id_ge is not None:
        query = query.filter(BusStop.id >= qParam.id_ge)
    if qParam.id_le is not None:
        query = query.filter(BusStop.id <= qParam.id_le)
    if qParam.id_list is not None:
        query = query.filter(BusStop.id.in_(qParam.id_list))
    if qParam.name is not None:
        query = query.filter(BusStop.name.ilike(f"%{qParam.name}%"))
    if qParam.landmark_id is not None:
        query = query.filter(BusStop.landmark_id == qParam.landmark_id)
    if qParam.created_on is not None:
        query = query.filter(BusStop.created_on == qParam.created_on)
    if qParam.created_on_ge is not None:
        query = query.filter(BusStop.created_on >= qParam.created_on_ge)
    if qParam.created_on_le is not None:
        query = query.filter(BusStop.created_on <= qParam.created_on_le)
    if qParam.updated_on is not None:
        query = query.filter(BusStop.updated_on == qParam.updated_on)
    if qParam.updated_on_ge is not None:
        query = query.filter(BusStop.updated_on >= qParam.updated_on_ge)
    if qParam.updated_on_le is not None:
        query = query.filter(BusStop.updated_on <= qParam.updated_on_le)
    if qParam.order_by == OrderBy.location and qParam.location:
        wktLocation = toWKTgeometry(qParam.location, Point)
        if wktLocation is None:
            raise exceptions.InvalidWKTStringOrType()
        if not isSRID4326(wktLocation):
            raise exceptions.InvalidSRID4326()
        orderQuery = func.ST_Distance(
            BusStop.location.cast(Geography), func.ST_GeogFromText(qParam.location)
        )
    else:
        orderQuery = getattr(BusStop, OrderBy(qParam.order_by).name)

    if qParam.order_in == OrderIn.ASC:
        query = query.order_by(orderQuery.asc())
    else:
        query = query.order_by(orderQuery.desc())
    query = query.offset(qParam.offset).limit(qParam.limit)
    busStops = query.all()
    for busStop in busStops:
        busStop.location = session.scalar(func.ST_AsText(busStop.location))
    return busStops


## API endpoints [Executive]
@route_executive.post(
    "/landmark/bus_stop",
    tags=["Bus Stop"],
    response_model=schemas.BusStop,
    status_code=status.HTTP_201_CREATED,
    responses=makeExceptionResponses(
        [
            exceptions.InvalidToken,
            exceptions.NoPermission,
            exceptions.InvalidWKTStringOrType,
            exceptions.InvalidSRID4326,
            exceptions.BusStopOutsideLandmark,
            exceptions.UnknownValue(BusStop.landmark_id),
        ]
    ),
    description="""
    Creates a new bus stop under a specified landmark with a valid SRID 4326 location.

    - Accepts a WKT point representing the bus stop location. Only SRID 4326 (WGS 84) geometries are allowed.
    - Validates geometry format and SRID.
    - Ensures the point lies within the boundary of the referenced landmark.
    - Only executives with the required permission (`create_bus_stop`) can access this endpoint.
    - Logs the bus stop creation activity with the associated token.
    """,
)
async def create_bus_stop(
    landmark_id: Annotated[int, Form()],
    location: Annotated[str, Form(description="Accepts only SRID 4326 (WGS84)")],
    name: Annotated[str | None, Form(max_length=128)] = None,
    bearer=Depends(bearer_executive),
    request_info=Depends(getRequestInfo),
):
    try:
        session = sessionMaker()
        token = getExecutiveToken(bearer.credentials, session)
        if token is None:
            raise exceptions.InvalidToken()
        role = getExecutiveRole(token, session)
        canCreateBusStop = bool(role and role.create_bus_stop)
        if not canCreateBusStop:
            raise exceptions.NoPermission()

        landmark = session.query(Landmark).filter(Landmark.id == landmark_id).first()
        if landmark is None:
            raise exceptions.UnknownValue(BusStop.landmark_id)
        wktLocation = toWKTgeometry(location, Point)
        if wktLocation is None:
            raise exceptions.InvalidWKTStringOrType()
        if not isSRID4326(wktLocation):
            raise exceptions.InvalidSRID4326()

        name = name or landmark.name
        location4326 = func.ST_SetSRID(func.ST_GeomFromText(location), EPSG_4326)
        withinBoundary = session.scalar(func.ST_Within(location4326, landmark.boundary))
        if not withinBoundary:
            raise exceptions.BusStopOutsideLandmark()

        busStop = BusStop(landmark_id=landmark_id, location=location, name=name)
        session.add(busStop)
        session.commit()
        logExecutiveEvent(token, request_info, jsonable_encoder(busStop))
        return busStop
    except Exception as e:
        exceptions.handle(e)
    finally:
        session.close()


@route_executive.patch(
    "/landmark/bus_stop",
    tags=["Bus Stop"],
    response_model=schemas.BusStop,
    responses=makeExceptionResponses(
        [
            exceptions.InvalidToken,
            exceptions.NoPermission,
            exceptions.InvalidWKTStringOrType,
            exceptions.InvalidSRID4326,
            exceptions.BusStopOutsideLandmark,
            exceptions.InvalidIdentifier,
        ]
    ),
    description="""
    Updates an existing bus stop with provided fields.

    - Accepts updates to `name` and `location` (WKT).
    - Ensures the WKT location is valid, SRID 4326, and inside the associated landmark boundary.
    - Only executives with the `update_bus_stop` permission can update bus stops.
    - Logs updates only if any field was changed.
    """,
)
async def update_bus_stop(
    id: Annotated[int, Form()],
    name: Annotated[str | None, Form(max_length=128)] = None,
    location: Annotated[
        str | None, Form(description="Accepts only SRID 4326 (WGS84)")
    ] = None,
    bearer=Depends(bearer_executive),
    request_info=Depends(getRequestInfo),
):
    try:
        session = sessionMaker()
        token = getExecutiveToken(bearer.credentials, session)
        if token is None:
            raise exceptions.InvalidToken()

        role = getExecutiveRole(token, session)
        canUpdateBusStop = bool(role and role.update_bus_stop)
        if not canUpdateBusStop:
            raise exceptions.NoPermission()

        busStop = session.query(BusStop).filter(BusStop.id == id).first()
        if busStop is None:
            raise exceptions.InvalidIdentifier()
        if name is not None and busStop.name != name:
            busStop.name = name

        if location is not None:
            wktLocation = toWKTgeometry(location, Point)
            if wktLocation is None:
                raise exceptions.InvalidWKTStringOrType()
            if not isSRID4326(wktLocation):
                raise exceptions.InvalidSRID4326()
            landmark = (
                session.query(Landmark)
                .filter(Landmark.id == busStop.landmark_id)
                .first()
            )
            location4326 = func.ST_SetSRID(func.ST_GeomFromText(location), EPSG_4326)
            withinBoundary = session.scalar(
                func.ST_Within(location4326, landmark.boundary)
            )
            if not withinBoundary:
                raise exceptions.BusStopOutsideLandmark()
            busStop.location = location4326

        isModified = session.is_modified(busStop)
        if isModified:
            session.commit()
            session.refresh(busStop)

        busStopData = jsonable_encoder(busStop, exclude={"location"})
        busStopData["location"] = session.scalar(func.ST_AsText(busStop.location))

        if isModified:
            logExecutiveEvent(token, request_info, busStopData)
        return busStopData
    except Exception as e:
        exceptions.handle(e)
    finally:
        session.close()


@route_executive.delete(
    "/landmark/bus_stop",
    tags=["Bus Stop"],
    status_code=status.HTTP_204_NO_CONTENT,
    responses=makeExceptionResponses(
        [
            exceptions.InvalidToken,
            exceptions.NoPermission,
        ]
    ),
    description="""
    Deletes a bus stop using its ID.

    - Only executives with the required permission (`delete_bus_stop`) can access this endpoint.
    - Validates the bus stop ID.
    - Logs the deletion activity with the associated executive token.
    """,
)
async def delete_bus_stop(
    id: Annotated[int, Form()],
    bearer=Depends(bearer_executive),
    request_info=Depends(getRequestInfo),
):
    try:
        session = sessionMaker()
        token = getExecutiveToken(bearer.credentials, session)
        if token is None:
            raise exceptions.InvalidToken()
        role = getExecutiveRole(token, session)
        canDeleteBusStop = bool(role and role.delete_bus_stop)
        if not canDeleteBusStop:
            raise exceptions.NoPermission()

        busStop = session.query(BusStop).filter(BusStop.id == id).first()
        if busStop:
            busStopData = jsonable_encoder(busStop, exclude={"location"})
            busStopData["location"] = session.scalar(func.ST_AsText(busStop.location))
            session.delete(busStop)
            session.commit()
            logExecutiveEvent(token, request_info, busStopData)
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    except Exception as e:
        exceptions.handle(e)
    finally:
        session.close()


@route_executive.get(
    "/landmark/bus_stop",
    tags=["Bus Stop"],
    response_model=List[schemas.BusStop],
    responses=makeExceptionResponses(
        [
            exceptions.InvalidToken,
            exceptions.InvalidWKTStringOrType,
            exceptions.InvalidSRID4326,
        ]
    ),
    description="""
    Fetches a list of bus stops filtered by optional query parameters.
    
    - The authenticated user can access this endpoint.
    - Supports filtering by ID range, ID list, location, name, and creation timestamps.
    - Support distance-based filtering when order_by is set to location and the location parameter is provided
    - Supports pagination with `offset` and `limit`.
    - Supports sorting using `order_by` and `order_in`.
    """,
)
async def fetch_bus_stops(
    qParam: BusStopQueryParams = Depends(), bearer=Depends(bearer_executive)
):
    try:
        session = sessionMaker()
        token = getExecutiveToken(bearer.credentials, session)
        if token is None:
            raise exceptions.InvalidToken()

        return queryBusStops(session, qParam)
    except Exception as e:
        exceptions.handle(e)
    finally:
        session.close()


## API endpoints [Operator]
@route_operator.get(
    "/landmark/bus_stop",
    tags=["Bus Stop"],
    response_model=List[schemas.BusStop],
    responses=makeExceptionResponses(
        [
            exceptions.InvalidToken,
            exceptions.InvalidWKTStringOrType,
            exceptions.InvalidSRID4326,
        ]
    ),
    description="""
    Fetches a list of bus stops filtered by optional query parameters.
    
    - The authenticated user can access this endpoint.
    - Supports filtering by ID range, ID list, location, name, and creation timestamps.
    - Support distance-based filtering when order_by is set to location and the location parameter is provided.
    - Supports pagination with `offset` and `limit`.
    - Supports sorting using `order_by` and `order_in`.
    """,
)
async def fetch_bus_stops(
    qParam: BusStopQueryParams = Depends(), bearer=Depends(bearer_operator)
):
    try:
        session = sessionMaker()
        token = getOperatorToken(bearer.credentials, session)
        if token is None:
            raise exceptions.InvalidToken()

        return queryBusStops(session, qParam)
    except Exception as e:
        exceptions.handle(e)
    finally:
        session.close()


## API endpoints [Vendor]
@route_vendor.get(
    "/landmark/bus_stop",
    tags=["Bus Stop"],
    response_model=List[schemas.BusStop],
    responses=makeExceptionResponses(
        [
            exceptions.InvalidToken,
            exceptions.InvalidWKTStringOrType,
            exceptions.InvalidSRID4326,
        ]
    ),
    description="""
    Fetches a list of bus stops filtered by optional query parameters.
    
    - The authenticated user can access this endpoint.
    - Supports filtering by ID range, ID list, location, name, and creation timestamps.
    - Support distance-based filtering when order_by is set to location and the location parameter is provided
    - Supports pagination with `offset` and `limit`.
    - Supports sorting using `order_by` and `order_in`.
    """,
)
async def fetch_bus_stops(
    qParam: BusStopQueryParams = Depends(), bearer=Depends(bearer_vendor)
):
    try:
        session = sessionMaker()
        token = getVendorToken(bearer.credentials, session)
        if token is None:
            raise exceptions.InvalidToken()

        return queryBusStops(session, qParam)
    except Exception as e:
        exceptions.handle(e)
    finally:
        session.close()
