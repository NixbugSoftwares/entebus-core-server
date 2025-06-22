from datetime import datetime
from enum import IntEnum
from typing import List, Optional
from fastapi import (
    APIRouter,
    Depends,
    Query,
    Response,
    status,
    Form,
)
from sqlalchemy.orm.session import Session
from fastapi.encoders import jsonable_encoder
from pydantic import BaseModel, Field
from shapely.geometry import Polygon
from shapely import wkt, wkb
from sqlalchemy import func
from geoalchemy2 import Geography

from app.api.bearer import bearer_executive, bearer_operator, bearer_vendor
from app.src.constants import MAX_LANDMARK_AREA, MIN_LANDMARK_AREA
from app.src.db import BusStop, Landmark, ExecutiveRole, Landmark, sessionMaker
from app.src import exceptions, validators, getters
from app.src.enums import LandmarkType
from app.src.loggers import logEvent
from app.src.functions import enumStr, getArea, makeExceptionResponses

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
        raise exceptions.InvalidLandmarkBoundaryArea()
    fParam.boundary = wkt.dumps(boundaryGeom)


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
    "/landmark",
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
        ]
    ),
    description="""
    """,
)
async def create_landmark(
    fParam: CreateForm = Depends(),
    bearer=Depends(bearer_executive),
    request_info=Depends(getters.requestInfo),
):
    try:
        session = sessionMaker()
        token = validators.executiveToken(bearer.credentials, session)
        role = getters.executiveRole(token, session)
        validators.executivePermission(role, ExecutiveRole.create_landmark)

        validateBoundary(fParam)
        landmark = Landmark(
            name=fParam.name,
            boundary=fParam.boundary,
            type=fParam.type,
        )
        session.add(landmark)
        session.commit()
        logEvent(token, request_info, jsonable_encoder(landmark))
        return landmark
    except Exception as e:
        exceptions.handle(e)
    finally:
        session.close()


@route_executive.patch(
    "/landmark",
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
            exceptions.InvalidLandmarkBoundaryArea,
            exceptions.BusStopOutsideLandmark,
        ]
    ),
    description="""
    """,
)
async def update_landmark(
    fParam: UpdateForm = Depends(),
    bearer=Depends(bearer_executive),
    request_info=Depends(getters.requestInfo),
):
    try:
        session = sessionMaker()
        token = validators.executiveToken(bearer.credentials, session)
        role = getters.executiveRole(token, session)
        validators.executivePermission(role, ExecutiveRole.update_landmark)

        landmark = session.query(Landmark).filter(Landmark.id == fParam.id).first()
        if landmark is None:
            raise exceptions.InvalidIdentifier()

        if fParam.name is not None and landmark.name != fParam.name:
            landmark.name = fParam.name
        if fParam.boundary is not None:
            boundaryGeom = validateBoundary(fParam)
            currentBoundary = (wkb.loads(bytes(landmark.boundary.data))).wkt
            if currentBoundary != fParam.boundary:
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
        if fParam.type is not None and landmark.type != fParam.type:
            landmark.type = fParam.type

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
        session.close()


@route_executive.delete(
    "/landmark",
    tags=["Landmark"],
    status_code=status.HTTP_204_NO_CONTENT,
    responses=makeExceptionResponses(
        [exceptions.InvalidToken, exceptions.NoPermission]
    ),
    description="""
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
    "/landmark",
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
    "/landmark",
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
    "/landmark",
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
