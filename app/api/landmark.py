from datetime import datetime
from typing import Annotated, List
from fastapi import APIRouter, Depends, Form, status, Query
from sqlalchemy.orm.session import Session
from fastapi.encoders import jsonable_encoder
from shapely import Polygon, Point
from sqlalchemy import func
from enum import IntEnum
from geoalchemy2 import Geography

from app.api.bearer import bearer_executive, bearer_operator, bearer_vendor
from app.src import schemas, exceptions
from app.src.constants import (
    EPSG_3857,
    EPSG_4326,
    MAX_LANDMARK_AREA,
    MIN_LANDMARK_AREA,
)
from app.src.db import sessionMaker, Landmark, BusStop
from app.src.enums import LandmarkType, OrderIn
from app.src.functions import (
    enumStr,
    getExecutiveRole,
    getExecutiveToken,
    getRequestInfo,
    isAABB,
    isSRID4326,
    logExecutiveEvent,
    makeExceptionResponses,
    toWKTgeometry,
    getOperatorToken,
    getVendorToken,
)

route_operator = APIRouter()
route_executive = APIRouter()
route_vendor = APIRouter()


## Schemas
class OrderBy(IntEnum):
    id = 1
    boundary = 2
    created_on = 3
    updated_on = 4


class LandmarkQueryParams:
    def __init__(
        self,
        id: int | None = Query(default=None),
        id_ge: int | None = Query(default=None),
        id_le: int | None = Query(default=None),
        id_list: List[int | None] = Query(
            default=None,
        ),
        name: str | None = Query(default=None),
        location: str | None = Query(
            default=None, description="Accepts only SRID 4326 (WGS84)"
        ),
        type: LandmarkType | None = Query(
            default=None, description=enumStr(LandmarkType)
        ),
        type_list: List[LandmarkType | None] = Query(
            default=None, description=enumStr(LandmarkType)
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
        self.type = type
        self.type_list = type_list
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
def queryLandmarks(session: Session, qParam: LandmarkQueryParams) -> List[Landmark]:
    query = session.query(Landmark)
    if qParam.id is not None:
        query = query.filter(Landmark.id == qParam.id)
    if qParam.id_ge is not None:
        query = query.filter(Landmark.id >= qParam.id_ge)
    if qParam.id_le is not None:
        query = query.filter(Landmark.id <= qParam.id_le)
    if qParam.id_list is not None:
        query = query.filter(Landmark.id.in_(qParam.id_list))
    if qParam.name is not None:
        query = query.filter(Landmark.name.ilike(f"%{qParam.name}%"))
    if qParam.type is not None:
        query = query.filter(Landmark.type == qParam.type)
    if qParam.type_list is not None:
        query = query.filter(Landmark.type.in_(qParam.type_list))
    if qParam.created_on is not None:
        query = query.filter(Landmark.created_on == qParam.created_on)
    if qParam.created_on_ge is not None:
        query = query.filter(Landmark.created_on >= qParam.created_on_ge)
    if qParam.created_on_le is not None:
        query = query.filter(Landmark.created_on <= qParam.created_on_le)
    if qParam.updated_on is not None:
        query = query.filter(Landmark.updated_on == qParam.updated_on)
    if qParam.updated_on_ge is not None:
        query = query.filter(Landmark.updated_on >= qParam.updated_on_ge)
    if qParam.updated_on_le is not None:
        query = query.filter(Landmark.updated_on <= qParam.updated_on_le)
    if qParam.order_by == OrderBy.boundary and qParam.location:
        wktLocation = toWKTgeometry(qParam.location, Point)
        if wktLocation is None:
            raise exceptions.InvalidWKTStringOrType()
        if not isSRID4326(wktLocation):
            raise exceptions.InvalidSRID4326()
        orderQuery = func.ST_Distance(
            Landmark.boundary.cast(Geography), func.ST_GeogFromText(qParam.location)
        )
    else:
        orderQuery = getattr(Landmark, OrderBy(qParam.order_by).name)

    if qParam.order_in == OrderIn.ASC:
        query = query.order_by(orderQuery.asc())
    else:
        query = query.order_by(orderQuery.desc())
    query = query.offset(qParam.offset).limit(qParam.limit)
    landmarks = query.all()
    for landmark in landmarks:
        landmark.boundary = session.scalar(func.ST_AsText(landmark.boundary))
    return landmarks


## API endpoints [Executive]
@route_executive.post(
    "/landmark",
    tags=["Landmark"],
    response_model=schemas.Landmark,
    status_code=status.HTTP_201_CREATED,
    responses=makeExceptionResponses(
        [
            exceptions.InvalidToken,
            exceptions.NoPermission,
            exceptions.InvalidWKTStringOrType,
            exceptions.InvalidSRID4326,
            exceptions.InvalidAABB,
            exceptions.OverlappingLandmarkBoundary,
            exceptions.InvalidLandmarkBoundaryArea,
        ]
    ),
    description="""
    Creates a new landmark for the executive with a valid SRID 4326 boundary.

    - Accepts a WKT polygon representing the landmark boundary. Only **AABB (axis-aligned bounding box)** geometries are allowed.
    - Validates geometry format, SRID (must be 4326 - WGS 84), and boundary area (must be within acceptable limits).
    - Ensures the boundary does not **overlap with existing landmarks** in the database.
    - Only executives with the required permission (`create_landmark`) can access this endpoint.
    - Logs the landmark creation activity with the associated token.
    """,
)
async def create_landmark(
    name: Annotated[str, Form(max_length=32)],
    boundary: Annotated[str, Form(description="Accepts only SRID 4326 (WGS84)")],
    type: Annotated[
        LandmarkType, Form(description=enumStr(LandmarkType))
    ] = LandmarkType.LOCAL,
    bearer=Depends(bearer_executive),
    request_info=Depends(getRequestInfo),
):
    try:
        session = sessionMaker()
        token = getExecutiveToken(bearer.credentials, session)
        if token is None:
            raise exceptions.InvalidToken()
        role = getExecutiveRole(token, session)
        canCreateLandmark = bool(role and role.create_landmark)
        if not canCreateLandmark:
            raise exceptions.NoPermission()

        wktBoundary = toWKTgeometry(boundary, Polygon)
        if wktBoundary is None:
            raise exceptions.InvalidWKTStringOrType()
        if not isSRID4326(wktBoundary):
            raise exceptions.InvalidSRID4326()
        if not isAABB(wktBoundary):
            raise exceptions.InvalidAABB()

        boundary4326 = func.ST_SetSRID(func.ST_GeomFromText(boundary), EPSG_4326)
        boundary3857 = func.ST_Transform(boundary4326, EPSG_3857)

        areaInSQmeters = session.scalar(func.ST_Area(boundary3857))
        landmark3857 = func.ST_Transform(Landmark.boundary, EPSG_3857)
        overlapping = (
            session.query(Landmark)
            .filter(func.ST_Intersects(landmark3857, boundary3857))
            .first()
        )
        if overlapping:
            raise exceptions.OverlappingLandmarkBoundary()
        if not (MIN_LANDMARK_AREA < areaInSQmeters < MAX_LANDMARK_AREA):
            raise exceptions.InvalidLandmarkBoundaryArea()

        landmark = Landmark(name=name, type=type, boundary=boundary)
        session.add(landmark)
        session.commit()
        logExecutiveEvent(token, request_info, jsonable_encoder(landmark))
        return landmark
    except Exception as e:
        exceptions.handle(e)
    finally:
        session.close()


@route_executive.patch(
    "/landmark",
    tags=["Landmark"],
    response_model=schemas.Landmark,
    responses=makeExceptionResponses(
        [
            exceptions.InvalidToken,
            exceptions.NoPermission,
            exceptions.InvalidIdentifier,
            exceptions.InvalidWKTStringOrType,
            exceptions.InvalidSRID4326,
            exceptions.InvalidAABB,
            exceptions.OverlappingLandmarkBoundary,
            exceptions.InvalidLandmarkBoundaryArea,
            exceptions.InvalidBusStopLocation,
        ]
    ),
    description="""
    Update an existing landmark by the executive with a valid SRID 4326 boundary.

    - Accepts a WKT polygon representing the landmark boundary. Only **AABB (axis-aligned bounding box)** geometries are allowed.
    - Validates geometry format, SRID (must be 4326 - WGS 84), and boundary area (must be within acceptable limits).
    - Ensures the boundary does not **overlap with existing landmarks** in the database.
    - Only executives with the required permission (`update_landmark`) can access this endpoint.
    - Logs the landmark creation activity with the associated token.
    """,
)
async def update_landmark(
    id: Annotated[int, Form()],
    name: Annotated[str | None, Form(max_length=128)] = None,
    boundary: Annotated[
        str | None, Form(description="Accepts only SRID 4326 (WGS84)")
    ] = None,
    type: Annotated[
        LandmarkType | None, Form(description=enumStr(LandmarkType))
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
        canUpdateLandmark = bool(role and role.update_landmark)
        if not canUpdateLandmark:
            raise exceptions.NoPermission()

        landmark = session.query(Landmark).filter(Landmark.id == id).first()
        if landmark is None:
            raise exceptions.InvalidIdentifier()

        if name is not None and landmark.name != name:
            landmark.name = name
        if type is not None and landmark.type != type:
            landmark.type = type
        if boundary is not None:
            wktBoundary = toWKTgeometry(boundary, Polygon)
            if wktBoundary is None:
                raise exceptions.InvalidWKTStringOrType()
            if not isSRID4326(wktBoundary):
                raise exceptions.InvalidSRID4326()
            if not isAABB(wktBoundary):
                raise exceptions.InvalidAABB()

            if landmark.boundary != boundary:
                boundary4326 = func.ST_SetSRID(
                    func.ST_GeomFromText(boundary), EPSG_4326
                )
                boundary3857 = func.ST_Transform(boundary4326, EPSG_3857)

                areaInSQmeters = session.scalar(func.ST_Area(boundary3857))
                landmark3857 = func.ST_Transform(Landmark.boundary, EPSG_3857)
                overlapping    = (session.query(Landmark)
                                  .filter(Landmark.id != id, func.ST_Intersects(landmark3857, boundary3857))
                                  .first())
                if overlapping:
                    raise exceptions.OverlappingLandmarkBoundary()
                if not (MIN_LANDMARK_AREA < areaInSQmeters < MAX_LANDMARK_AREA):
                    raise exceptions.InvalidLandmarkBoundaryArea()

                busStops = (
                    session.query(BusStop).filter(BusStop.landmark_id == id).all()
                )
                for busStop in busStops:
                    withinBoundary = session.scalar(
                        func.ST_Within(busStop.location, boundary4326)
                    )
                    if not withinBoundary:
                        raise exceptions.InvalidBusStopLocation()
                landmark.boundary = boundary
        landmark.version += 1

        isModified = session.is_modified(landmark)
        if isModified:
            session.commit()
            session.refresh(landmark)

        landmarkData = jsonable_encoder(landmark, exclude={"boundary"})
        landmarkData["boundary"] = session.scalar(func.ST_AsText(landmark.boundary))
        
        if isModified:
            logExecutiveEvent(token, request_info, landmarkData)
        return landmarkData
    except Exception as e:
        exceptions.handle(e)
    finally:
        session.close()


@route_executive.get(
    "/landmark",
    tags=["Landmark"],
    response_model=List[schemas.Landmark],
    responses=makeExceptionResponses(
        [
            exceptions.InvalidToken,
            exceptions.InvalidWKTStringOrType,
            exceptions.InvalidSRID4326,
        ]
    ),
    description="""
    Fetches a list of landmark filtered by optional query parameters.
    
    - The authenticated user can access this endpoint.
    - Supports filtering by ID range, ID list, location, type_list, name, and creation timestamps.
    - Support distance-based filtering when order_by is set to location and the location parameter is provided
    - Supports pagination with `offset` and `limit`.
    - Supports sorting using `order_by` and `order_in`.
    """,
)
async def fetch_landmarks(
    qParam: LandmarkQueryParams = Depends(), bearer=Depends(bearer_executive)
):
    try:
        session = sessionMaker()
        token = getExecutiveToken(bearer.credentials, session)
        if token is None:
            raise exceptions.InvalidToken()

        return queryLandmarks(session, qParam)
    except Exception as e:
        exceptions.handle(e)
    finally:
        session.close()


@route_executive.delete("/landmark", tags=["Landmark"])
async def delete_landmark(bearer=Depends(bearer_executive)):
    pass


## API endpoints [Operator]
@route_operator.get(
    "/landmark",
    tags=["Landmark"],
    response_model=List[schemas.Landmark],
    responses=makeExceptionResponses(
        [
            exceptions.InvalidToken,
            exceptions.InvalidWKTStringOrType,
            exceptions.InvalidSRID4326,
        ]
    ),
    description="""
    Fetches a list of landmark filtered by optional query parameters.
    
    - The authenticated user can access this endpoint.
    - Supports filtering by ID range, ID list, location, type_list, name, and creation timestamps.
    - Support distance-based filtering when order_by is set to location and the location parameter is provided
    - Supports pagination with `offset` and `limit`.
    - Supports sorting using `order_by` and `order_in`.
    """,
)
async def fetch_landmarks(
    qParam: LandmarkQueryParams = Depends(), bearer=Depends(bearer_operator)
):
    try:
        session = sessionMaker()
        token = getOperatorToken(bearer.credentials, session)
        if token is None:
            raise exceptions.InvalidToken()

        return queryLandmarks(session, qParam)
    except Exception as e:
        exceptions.handle(e)
    finally:
        session.close()


## API endpoints [Vendor]
@route_vendor.get(
    "/landmark",
    tags=["Landmark"],
    response_model=List[schemas.Landmark],
    responses=makeExceptionResponses(
        [
            exceptions.InvalidToken,
            exceptions.InvalidWKTStringOrType,
            exceptions.InvalidSRID4326,
        ]
    ),
    description="""
    Fetches a list of landmark filtered by optional query parameters.
    
    - The authenticated user can access this endpoint.
    - Supports filtering by ID range, ID list, location, type_list, name, and creation timestamps.
    - Support distance-based filtering when order_by is set to location and the location parameter is provided
    - Supports pagination with `offset` and `limit`.
    - Supports sorting using `order_by` and `order_in`.
    """,
)
async def fetch_landmarks(
    qParam: LandmarkQueryParams = Depends(), bearer=Depends(bearer_vendor)
):
    try:
        session = sessionMaker()
        token = getVendorToken(bearer.credentials, session)
        if token is None:
            raise exceptions.InvalidToken()

        return queryLandmarks(session, qParam)
    except Exception as e:
        exceptions.handle(e)
    finally:
        session.close()
