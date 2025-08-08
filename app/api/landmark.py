from datetime import datetime
from enum import IntEnum
from typing import List, Optional
from fastapi import APIRouter, Depends, Query, Response, status, Form
from sqlalchemy.orm.session import Session
from fastapi.encoders import jsonable_encoder
from pydantic import BaseModel, Field
from shapely.geometry import Polygon, Point
from shapely import wkt, wkb
from sqlalchemy import func
from geoalchemy2 import Geography

from app.api.bearer import bearer_executive, bearer_operator, bearer_vendor
from app.src.constants import MAX_LANDMARK_AREA, MIN_LANDMARK_AREA, EPSG_4326
from app.src.db import BusStop, Landmark, ExecutiveRole, Landmark, sessionMaker
from app.src import exceptions, validators, getters
from app.src.enums import LandmarkType
from app.src.loggers import logEvent
from app.src.functions import enumStr, getArea, makeExceptionResponses, updateIfChanged
from app.src.urls import URL_LANDMARK
from app.src.redis import acquireLock, releaseLock

route_executive = APIRouter()
route_vendor = APIRouter()
route_operator = APIRouter()


## Output Schema
class LandmarkSchema(BaseModel):
    id: int
    name: str
    version: int
    boundary: str
    type: int
    updated_on: Optional[datetime]
    created_on: datetime


## Input Forms
class CreateForm(BaseModel):
    name: str = Field(Form(max_length=32))
    boundary: str = Field(Form(description="Accepts only SRID 4326 (WGS84)"))
    type: LandmarkType = Field(
        Form(description=enumStr(LandmarkType), default=LandmarkType.LOCAL)
    )


class UpdateForm(BaseModel):
    id: int | None = Field(Form())
    name: str | None = Field(Form(max_length=32, default=None))
    boundary: str | None = Field(
        Form(default=None, description="Accepts only SRID 4326 (WGS84)")
    )
    type: LandmarkType | None = Field(
        Form(description=enumStr(LandmarkType), default=None)
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
    # type based
    type: LandmarkType | None = Field(
        Query(default=None, description=enumStr(LandmarkType))
    )
    type_list: List[LandmarkType] | None = Field(
        Query(default=None, description=enumStr(LandmarkType))
    )
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
def validateBoundary(fParam: CreateForm | UpdateForm) -> Polygon:
    # Validate the WKT polygon input string
    boundaryGeom = validators.WKTstring(fParam.boundary, Polygon)
    validators.SRID4326(boundaryGeom)
    validators.AABB(boundaryGeom)

    # Validate the boundary area
    areaInSQmeters = getArea(boundaryGeom)
    if not (MIN_LANDMARK_AREA < areaInSQmeters < MAX_LANDMARK_AREA):
        raise exceptions.InvalidBoundaryArea()
    fParam.boundary = wkt.dumps(boundaryGeom)
    return boundaryGeom


def searchLandmark(session: Session, qParam: QueryParams) -> List[Landmark]:
    query = session.query(Landmark)

    # Pre-processing
    if qParam.location is not None:
        geometry = validators.WKTstring(qParam.location, Point)
        validators.SRID4326(geometry)
        qParam.location = wkt.dumps(geometry)

    # Filters
    if qParam.name is not None:
        query = query.filter(Landmark.name.ilike(f"%{qParam.name}%"))
    # id based
    if qParam.id is not None:
        query = query.filter(Landmark.id == qParam.id)
    if qParam.id_ge is not None:
        query = query.filter(Landmark.id >= qParam.id_ge)
    if qParam.id_le is not None:
        query = query.filter(Landmark.id <= qParam.id_le)
    if qParam.id_list is not None:
        query = query.filter(Landmark.id.in_(qParam.id_list))
    # type based
    if qParam.type is not None:
        query = query.filter(Landmark.type == qParam.type)
    if qParam.type_list is not None:
        query = query.filter(Landmark.type.in_(qParam.type_list))
    # updated_on based
    if qParam.updated_on_ge is not None:
        query = query.filter(Landmark.updated_on >= qParam.updated_on_ge)
    if qParam.updated_on_le is not None:
        query = query.filter(Landmark.updated_on <= qParam.updated_on_le)
    # created_on based
    if qParam.created_on_ge is not None:
        query = query.filter(Landmark.created_on >= qParam.created_on_ge)
    if qParam.created_on_le is not None:
        query = query.filter(Landmark.created_on <= qParam.created_on_le)

    # Ordering
    if qParam.order_by == OrderBy.location:
        if qParam.location is not None:
            orderingAttribute = func.ST_Distance(
                Landmark.boundary.cast(Geography), func.ST_GeogFromText(qParam.location)
            )
        else:
            orderingAttribute = Landmark.boundary
    else:
        orderingAttribute = getattr(Landmark, OrderBy(qParam.order_by).name)
    if qParam.order_in == OrderIn.ASC:
        query = query.order_by(orderingAttribute.asc())
    else:
        query = query.order_by(orderingAttribute.desc())

    # Pagination
    query = query.offset(qParam.offset).limit(qParam.limit)
    landmarks = query.all()

    # Post-processing
    for landmark in landmarks:
        landmark.boundary = (wkb.loads(bytes(landmark.boundary.data))).wkt
    return landmarks


## API endpoints [Executive]
@route_executive.post(
    URL_LANDMARK,
    tags=["Landmark"],
    response_model=LandmarkSchema,
    status_code=status.HTTP_201_CREATED,
    responses=makeExceptionResponses(
        [
            exceptions.InvalidToken,
            exceptions.NoPermission,
            exceptions.InvalidWKTStringOrType,
            exceptions.InvalidSRID4326,
            exceptions.InvalidAABB,
            exceptions.InvalidBoundaryArea,
            exceptions.OverlappingLandmarkBoundary,
        ]
    ),
    description="""
    Create a new landmark by specifying its name, type, and spatial boundary.  
    The boundary must be a valid AABB polygon in SRID 4326 (WGS84), and its area must be within an acceptable range.  
    Only executives with `create_landmark` permission can perform this operation.
    """,
)
async def create_landmark(
    fParam: CreateForm = Depends(),
    bearer=Depends(bearer_executive),
    request_info=Depends(getters.requestInfo),
):
    landmarkLock = None
    try:
        session = sessionMaker()
        token = validators.executiveToken(bearer.credentials, session)
        role = getters.executiveRole(token, session)
        validators.executivePermission(role, ExecutiveRole.create_landmark)

        landmarkLock = acquireLock(Landmark.__tablename__)
        # Check for overlapping with other landmarks
        boundaryGeom = validateBoundary(fParam)
        overlapping = (
            session.query(Landmark)
            .filter(
                func.ST_Intersects(
                    Landmark.boundary, func.ST_GeomFromText(boundaryGeom.wkt, EPSG_4326)
                )
            )
            .first()
        )
        if overlapping:
            raise exceptions.OverlappingLandmarkBoundary()
        landmark = Landmark(
            name=fParam.name,
            boundary=fParam.boundary,
            type=fParam.type,
        )
        session.add(landmark)
        session.commit()
        session.refresh(landmark)

        landmarkData = jsonable_encoder(landmark, exclude={"boundary"})
        landmarkData["boundary"] = (wkb.loads(bytes(landmark.boundary.data))).wkt
        logEvent(token, request_info, landmarkData)
        return landmarkData
    except Exception as e:
        exceptions.handle(e)
    finally:
        releaseLock(landmarkLock)
        session.close()


@route_executive.patch(
    URL_LANDMARK,
    tags=["Landmark"],
    response_model=LandmarkSchema,
    responses=makeExceptionResponses(
        [
            exceptions.InvalidToken,
            exceptions.NoPermission,
            exceptions.InvalidIdentifier,
            exceptions.InvalidWKTStringOrType,
            exceptions.InvalidSRID4326,
            exceptions.InvalidAABB,
            exceptions.InvalidBoundaryArea,
            exceptions.BusStopOutsideLandmark,
            exceptions.OverlappingLandmarkBoundary,
        ]
    ),
    description="""
    Update the details of an existing landmark including name, type, or boundary.  
    If the boundary is changed, all associated bus stops must remain within the new boundary.  
    Only executives with `update_landmark` permission can perform this operation.
    """,
)
async def update_landmark(
    fParam: UpdateForm = Depends(),
    bearer=Depends(bearer_executive),
    request_info=Depends(getters.requestInfo),
):
    landmarkLock = None
    try:
        session = sessionMaker()
        token = validators.executiveToken(bearer.credentials, session)
        role = getters.executiveRole(token, session)
        validators.executivePermission(role, ExecutiveRole.update_landmark)

        landmarkLock = acquireLock(Landmark.__tablename__)
        landmark = session.query(Landmark).filter(Landmark.id == fParam.id).first()
        if landmark is None:
            raise exceptions.InvalidIdentifier()

        updateIfChanged(landmark, fParam, [Landmark.name.key, Landmark.type.key])
        if fParam.boundary is not None:
            boundaryGeom = validateBoundary(fParam)
            currentBoundary = (wkb.loads(bytes(landmark.boundary.data))).wkt
            if currentBoundary != fParam.boundary:
                # Check for overlapping with other landmarks
                overlapping = (
                    session.query(Landmark)
                    .filter(
                        Landmark.id != fParam.id,
                        func.ST_Intersects(
                            Landmark.boundary,
                            func.ST_GeomFromText(boundaryGeom.wkt, EPSG_4326),
                        ),
                    )
                    .first()
                )
                if overlapping:
                    raise exceptions.OverlappingLandmarkBoundary()
                # Verify that all bus stops are inside the new boundary
                busStops = (
                    session.query(BusStop)
                    .filter(BusStop.landmark_id == fParam.id)
                    .all()
                )
                for busStop in busStops:
                    busStopGeom = wkb.loads(bytes(busStop.location.data))
                    if not busStopGeom.within(boundaryGeom):
                        raise exceptions.BusStopOutsideLandmark()
                landmark.boundary = fParam.boundary

        haveUpdates = session.is_modified(landmark)
        if haveUpdates:
            landmark.version += 1
            session.commit()
            session.refresh(landmark)

        landmarkData = jsonable_encoder(landmark, exclude={"boundary"})
        landmarkData["boundary"] = (wkb.loads(bytes(landmark.boundary.data))).wkt
        if haveUpdates:
            logEvent(token, request_info, landmarkData)
        return landmarkData
    except Exception as e:
        exceptions.handle(e)
    finally:
        releaseLock(landmarkLock)
        session.close()


@route_executive.delete(
    URL_LANDMARK,
    tags=["Landmark"],
    status_code=status.HTTP_204_NO_CONTENT,
    responses=makeExceptionResponses(
        [exceptions.InvalidToken, exceptions.NoPermission]
    ),
    description="""
    Delete an existing landmark by ID.  
    Only executives with `delete_landmark` permission can perform this action.  
    If the landmark exists, it will be permanently removed.
    """,
)
async def delete_landmark(
    fParam: DeleteForm = Depends(),
    bearer=Depends(bearer_executive),
    request_info=Depends(getters.requestInfo),
):
    try:
        session = sessionMaker()
        token = validators.executiveToken(bearer.credentials, session)
        role = getters.executiveRole(token, session)
        validators.executivePermission(role, ExecutiveRole.delete_landmark)

        landmark = session.query(Landmark).filter(Landmark.id == fParam.id).first()
        if landmark is not None:
            session.delete(landmark)
            session.commit()
            landmarkData = jsonable_encoder(landmark, exclude={"boundary"})
            landmarkData["boundary"] = (wkb.loads(bytes(landmark.boundary.data))).wkt
            logEvent(token, request_info, landmarkData)
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    except Exception as e:
        exceptions.handle(e)
    finally:
        session.close()


@route_executive.get(
    URL_LANDMARK,
    tags=["Landmark"],
    response_model=List[LandmarkSchema],
    responses=makeExceptionResponses(
        [
            exceptions.InvalidToken,
            exceptions.InvalidWKTStringOrType,
            exceptions.InvalidSRID4326,
        ]
    ),
    description="""
    Retrieve a list of landmarks with advanced filtering, sorting, and pagination.  
    Supports spatial queries using a reference location in SRID 4326, and ordering by proximity or metadata fields.  
    Only accessible to authenticated executives.
    """,
)
async def fetch_landmark(
    qParam: QueryParams = Depends(), bearer=Depends(bearer_executive)
):
    try:
        session = sessionMaker()
        validators.executiveToken(bearer.credentials, session)

        return searchLandmark(session, qParam)
    except Exception as e:
        exceptions.handle(e)
    finally:
        session.close()


## API endpoints [Vendor]
@route_vendor.get(
    URL_LANDMARK,
    tags=["Landmark"],
    response_model=List[LandmarkSchema],
    responses=makeExceptionResponses(
        [
            exceptions.InvalidToken,
            exceptions.InvalidWKTStringOrType,
            exceptions.InvalidSRID4326,
        ]
    ),
    description="""
    Retrieve a list of landmarks with filtering and sorting options available to vendor accounts.  
    Supports spatial filters like proximity to a point, and constraints on metadata fields such as creation date or type.
    """,
)
async def fetch_landmark(
    qParam: QueryParams = Depends(), bearer=Depends(bearer_vendor)
):
    try:
        session = sessionMaker()
        validators.vendorToken(bearer.credentials, session)

        return searchLandmark(session, qParam)
    except Exception as e:
        exceptions.handle(e)
    finally:
        session.close()


## API endpoints [Operator]
@route_operator.get(
    URL_LANDMARK,
    tags=["Landmark"],
    response_model=List[LandmarkSchema],
    responses=makeExceptionResponses(
        [
            exceptions.InvalidToken,
            exceptions.InvalidWKTStringOrType,
            exceptions.InvalidSRID4326,
        ]
    ),
    description="""
    Retrieve a list of landmarks available to operators.  
    Supports spatial and metadata-based querying with optional sorting and pagination features.
    """,
)
async def fetch_landmark(
    qParam: QueryParams = Depends(), bearer=Depends(bearer_operator)
):
    try:
        session = sessionMaker()
        validators.operatorToken(bearer.credentials, session)

        return searchLandmark(session, qParam)
    except Exception as e:
        exceptions.handle(e)
    finally:
        session.close()
