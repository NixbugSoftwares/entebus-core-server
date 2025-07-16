from datetime import datetime
from enum import IntEnum
from typing import List, Optional
from fastapi import APIRouter, Depends, Query, Response, status, Form
from sqlalchemy.orm.session import Session
from fastapi.encoders import jsonable_encoder
from pydantic import BaseModel, Field
from shapely.geometry import Point
from shapely import wkt, wkb
from sqlalchemy import func
from geoalchemy2 import Geography

from app.api.bearer import bearer_executive, bearer_operator, bearer_vendor
from app.src.db import BusStop, Landmark, sessionMaker
from app.src import exceptions, validators, getters
from app.src.loggers import logEvent
from app.src.functions import enumStr, makeExceptionResponses

route_executive = APIRouter()
route_vendor = APIRouter()
route_operator = APIRouter()


## Output Schema
class BusStopSchema(BaseModel):
    id: int
    name: str
    landmark_id: int
    location: str
    updated_on: Optional[datetime]
    created_on: datetime


## Input Forms
class CreateForm(BaseModel):
    name: str = Field(Form(max_length=128))
    landmark_id: int = Field(Form())
    location: str = Field(Form(description="Accepts only SRID 4326 (WGS84)"))


class UpdateForm(BaseModel):
    id: int = Field(Form())
    name: str | None = Field(Form(max_length=128, default=None))
    location: str | None = Field(
        Form(default=None, description="Accepts only SRID 4326 (WGS84)")
    )


class DeleteForm(BaseModel):
    id: int = Field(Form())


## Query Parameters
class OrderIn(IntEnum):
    ASC = 1
    DESC = 2


class OrderBy(IntEnum):
    id = 1
    location = 2
    updated_on = 3
    created_on = 4


class QueryParams(BaseModel):
    name: str | None = Field(Query(default=None))
    location: str | None = Field(
        Query(default=None, description="Accepts only SRID 4326 (WGS84)")
    )
    # id based
    id: int | None = Field(Query(default=None))
    id_ge: int | None = Field(Query(default=None))
    id_le: int | None = Field(Query(default=None))
    id_list: List[int] | None = Field(Query(default=None))
    # landmark_id based
    landmark_id: int | None = Field(Query(default=None))
    landmark_id_list: List[int] | None = Field(Query(default=None))
    # updated_on based
    updated_on_ge: datetime | None = Field(Query(default=None))
    updated_on_le: datetime | None = Field(Query(default=None))
    # created_on based
    created_on_ge: datetime | None = Field(Query(default=None))
    created_on_le: datetime | None = Field(Query(default=None))
    # Ordering
    order_by: OrderBy = Field(Query(default=OrderBy.id, description=enumStr(OrderBy)))
    order_in: OrderIn = Field(Query(default=OrderIn.DESC, description=enumStr(OrderIn)))
    # Pagination
    offset: int = Field(Query(default=0, ge=0))
    limit: int = Field(Query(default=20, gt=0, le=100))


## Function
def searchBusStop(session: Session, qParam: QueryParams) -> List[BusStop]:
    query = session.query(BusStop)

    # Pre-processing
    if qParam.location is not None:
        geometry = validators.WKTstring(qParam.location, Point)
        validators.SRID4326(geometry)
        qParam.location = wkt.dumps(geometry)

    # Filters
    if qParam.name is not None:
        query = query.filter(BusStop.name.ilike(f"%{qParam.name}%"))
    # id based
    if qParam.id is not None:
        query = query.filter(BusStop.id == qParam.id)
    if qParam.id_ge is not None:
        query = query.filter(BusStop.id >= qParam.id_ge)
    if qParam.id_le is not None:
        query = query.filter(BusStop.id <= qParam.id_le)
    if qParam.id_list is not None:
        query = query.filter(BusStop.id.in_(qParam.id_list))
    # landmark_id based
    if qParam.landmark_id is not None:
        query = query.filter(BusStop.landmark_id == qParam.landmark_id)
    if qParam.landmark_id_list is not None:
        query = query.filter(BusStop.landmark_id.in_(qParam.landmark_id_list))
    # updated_on based
    if qParam.updated_on_ge is not None:
        query = query.filter(BusStop.updated_on >= qParam.updated_on_ge)
    if qParam.updated_on_le is not None:
        query = query.filter(BusStop.updated_on <= qParam.updated_on_le)
    # created_on based
    if qParam.created_on_ge is not None:
        query = query.filter(BusStop.created_on >= qParam.created_on_ge)
    if qParam.created_on_le is not None:
        query = query.filter(BusStop.created_on <= qParam.created_on_le)

    # Ordering
    if qParam.order_by == OrderBy.location and qParam.location:
        orderingAttribute = func.ST_Distance(
            BusStop.location.cast(Geography), func.ST_GeogFromText(qParam.location)
        )
    else:
        orderingAttribute = getattr(BusStop, OrderBy(qParam.order_by).name)
    if qParam.order_in == OrderIn.ASC:
        query = query.order_by(orderingAttribute.asc())
    else:
        query = query.order_by(orderingAttribute.desc())

    # Pagination
    query = query.offset(qParam.offset).limit(qParam.limit)
    busStops = query.all()

    # Post-processing
    for busStop in busStops:
        busStop.location = (wkb.loads(bytes(busStop.location.data))).wkt
    return busStops


## API endpoints [Executive]
@route_executive.post(
    "/landmark/bus_stop",
    tags=["Bus Stop"],
    response_model=BusStopSchema,
    status_code=status.HTTP_201_CREATED,
    responses=makeExceptionResponses(
        [
            exceptions.InvalidToken,
            exceptions.NoPermission,
            exceptions.InvalidWKTStringOrType,
            exceptions.InvalidSRID4326,
            exceptions.UnknownValue(BusStop.landmark_id),
            exceptions.BusStopOutsideLandmark,
        ]
    ),
    description="""
    Create a new bus stop within a landmark boundary.  
    Validates location SRID and ensures the bus stop is geographically inside the target landmark.  
    Requires `create_landmark` or `update_landmark` permission.
    """,
)
async def create_bus_stop(
    fParam: CreateForm = Depends(),
    bearer=Depends(bearer_executive),
    request_info=Depends(getters.requestInfo),
):
    try:
        session = sessionMaker()
        token = validators.executiveToken(bearer.credentials, session)
        role = getters.executiveRole(token, session)
        if not (role.create_landmark | role.update_landmark):
            raise exceptions.NoPermission()

        locationGeom = validators.WKTstring(fParam.location, Point)
        validators.SRID4326(locationGeom)
        fParam.location = wkt.dumps(locationGeom)

        landmark = (
            session.query(Landmark).filter(Landmark.id == fParam.landmark_id).first()
        )
        if landmark is None:
            raise exceptions.UnknownValue(BusStop.landmark_id)

        boundaryGeom = wkb.loads(bytes(landmark.boundary.data))
        if not boundaryGeom.contains(locationGeom):
            raise exceptions.BusStopOutsideLandmark()

        busStop = BusStop(
            name=fParam.name,
            landmark_id=fParam.landmark_id,
            location=fParam.location,
        )
        session.add(busStop)
        session.commit()
        session.refresh(busStop)

        busStopData = jsonable_encoder(busStop, exclude={"location"})
        busStopData["location"] = (wkb.loads(bytes(busStop.location.data))).wkt
        logEvent(token, request_info, busStopData)
        return busStopData
    except Exception as e:
        exceptions.handle(e)
    finally:
        session.close()


@route_executive.patch(
    "/landmark/bus_stop",
    tags=["Bus Stop"],
    response_model=BusStopSchema,
    responses=makeExceptionResponses(
        [
            exceptions.InvalidToken,
            exceptions.NoPermission,
            exceptions.InvalidIdentifier,
            exceptions.InvalidWKTStringOrType,
            exceptions.InvalidSRID4326,
            exceptions.BusStopOutsideLandmark,
        ]
    ),
    description="""
    Update an existing bus stop's name and/or location.  
    If location is updated, it is validated against the landmark's boundary.  
    Requires `create_landmark` or `update_landmark` permission.
    """,
)
async def update_bus_stop(
    fParam: UpdateForm = Depends(),
    bearer=Depends(bearer_executive),
    request_info=Depends(getters.requestInfo),
):
    try:
        session = sessionMaker()
        token = validators.executiveToken(bearer.credentials, session)
        role = getters.executiveRole(token, session)
        if not (role.create_landmark | role.update_landmark):
            raise exceptions.NoPermission()

        busStop = session.query(BusStop).filter(BusStop.id == fParam.id).first()
        if busStop is None:
            raise exceptions.InvalidIdentifier()

        if fParam.name is not None and busStop.name != fParam.name:
            busStop.name = fParam.name
        if fParam.location is not None:
            locationGeom = validators.WKTstring(fParam.location, Point)
            validators.SRID4326(locationGeom)
            fParam.location = wkt.dumps(locationGeom)

            currentLocation = (wkb.loads(bytes(busStop.location.data))).wkt
            if currentLocation != fParam.location:
                landmark = (
                    session.query(Landmark)
                    .filter(Landmark.id == busStop.landmark_id)
                    .first()
                )

                boundaryGeom = wkb.loads(bytes(landmark.boundary.data))
                if not boundaryGeom.contains(locationGeom):
                    raise exceptions.BusStopOutsideLandmark()
                busStop.location = fParam.location

        haveUpdates = session.is_modified(busStop)
        if haveUpdates:
            session.commit()
            session.refresh(busStop)

        busStopData = jsonable_encoder(busStop, exclude={"location"})
        busStopData["location"] = (wkb.loads(bytes(busStop.location.data))).wkt
        if haveUpdates:
            logEvent(token, request_info, busStopData)
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
        [exceptions.InvalidToken, exceptions.NoPermission]
    ),
    description="""
    Delete a bus stop by ID.  
    Requires `create_landmark` or `update_landmark` permission.  
    Removes the record if it exists and logs the deletion event.
    """,
)
async def delete_bus_stop(
    fParam: DeleteForm = Depends(),
    bearer=Depends(bearer_executive),
    request_info=Depends(getters.requestInfo),
):
    try:
        session = sessionMaker()
        token = validators.executiveToken(bearer.credentials, session)
        role = getters.executiveRole(token, session)
        if not (role.create_landmark | role.update_landmark):
            raise exceptions.NoPermission()

        busStop = session.query(BusStop).filter(BusStop.id == fParam.id).first()
        if busStop is not None:
            session.delete(busStop)
            session.commit()

            busStopData = jsonable_encoder(busStop, exclude={"location"})
            busStopData["location"] = (wkb.loads(bytes(busStop.location.data))).wkt
            logEvent(token, request_info, busStopData)
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    except Exception as e:
        exceptions.handle(e)
    finally:
        session.close()


@route_executive.get(
    "/landmark/bus_stop",
    tags=["Bus Stop"],
    response_model=List[BusStopSchema],
    responses=makeExceptionResponses(
        [
            exceptions.InvalidToken,
            exceptions.InvalidWKTStringOrType,
            exceptions.InvalidSRID4326,
        ]
    ),
    description="""
    Retrieve bus stops based on flexible query filters.  
    Supports pagination and distance-based sorting when location is provided.  
    Requires a valid executive token.
    """,
)
async def fetch_bus_stop(
    qParam: QueryParams = Depends(), bearer=Depends(bearer_executive)
):
    try:
        session = sessionMaker()
        validators.executiveToken(bearer.credentials, session)

        return searchBusStop(session, qParam)
    except Exception as e:
        exceptions.handle(e)
    finally:
        session.close()


# ## API endpoints [Vendor]
@route_vendor.get(
    "/landmark/bus_stop",
    tags=["Bus Stop"],
    response_model=List[BusStopSchema],
    responses=makeExceptionResponses(
        [
            exceptions.InvalidToken,
            exceptions.InvalidWKTStringOrType,
            exceptions.InvalidSRID4326,
        ]
    ),
    description="""
    Retrieve bus stops based on flexible query filters.  
    Supports pagination and distance-based sorting when location is provided.  
    Requires a valid vendor token.
    """,
)
async def fetch_bus_stop(
    qParam: QueryParams = Depends(), bearer=Depends(bearer_vendor)
):
    try:
        session = sessionMaker()
        validators.vendorToken(bearer.credentials, session)

        return searchBusStop(session, qParam)
    except Exception as e:
        exceptions.handle(e)
    finally:
        session.close()


# ## API endpoints [Operator]
@route_operator.get(
    "/landmark/bus_stop",
    tags=["Bus Stop"],
    response_model=List[BusStopSchema],
    responses=makeExceptionResponses(
        [
            exceptions.InvalidToken,
            exceptions.InvalidWKTStringOrType,
            exceptions.InvalidSRID4326,
        ]
    ),
    description="""
    Retrieve bus stops based on flexible query filters.  
    Supports pagination and distance-based sorting when location is provided.  
    Requires a valid operator token.
    """,
)
async def fetch_bus_stop(
    qParam: QueryParams = Depends(), bearer=Depends(bearer_operator)
):
    try:
        session = sessionMaker()
        validators.operatorToken(bearer.credentials, session)

        return searchBusStop(session, qParam)
    except Exception as e:
        exceptions.handle(e)
    finally:
        session.close()
