from datetime import datetime
from typing import Annotated, List
from fastapi import APIRouter, Depends, Form, status, Query
from fastapi.encoders import jsonable_encoder
from shapely import Polygon
from sqlalchemy import func
from enum import IntEnum

from app.api.bearer import bearer_executive, bearer_operator, bearer_vendor
from app.src import schemas, exceptions
from app.src.constants import (
    EPSG_3857,
    EPSG_4326,
    MAX_LANDMARK_AREA,
    MIN_LANDMARK_AREA,
)
from app.src.enums import OrderIn
from app.src.db import sessionMaker, Landmark
from app.src.enums import LandmarkType
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
)

route_operator = APIRouter()
route_executive = APIRouter()
route_vendor = APIRouter()


## Schemas
class OrderBy(IntEnum):
    id = 1
    location = 3
    created_on = 4
    updated_on = 5


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
        type: LandmarkType | None = Query(default=None),
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


@route_executive.patch("/landmark", tags=["Landmark"])
async def update_landmark(bearer=Depends(bearer_executive)):
    pass


@route_executive.get("/landmark", tags=["Landmark"])
async def fetch_landmarks(bearer=Depends(bearer_executive)):
    pass


@route_executive.delete("/landmark", tags=["Landmark"])
async def delete_landmark(bearer=Depends(bearer_executive)):
    pass


## API endpoints [Operator]
@route_operator.get("/landmark", tags=["Landmark"])
async def fetch_landmarks(bearer=Depends(bearer_operator)):
    pass


## API endpoints [Vendor]
@route_vendor.get("/landmark", tags=["Landmark"])
async def fetch_landmarks(bearer=Depends(bearer_vendor)):
    pass
