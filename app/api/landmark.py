from typing import Annotated
from fastapi import APIRouter, Depends, Form, status
from fastapi.encoders import jsonable_encoder
from shapely import Polygon
from sqlalchemy import func

from app.api.bearer import bearer_executive, bearer_operator, bearer_vendor
from app.src import schemas, exceptions
from app.src.constants import EPSG_3857, EPSG_4326, MAX_LANDMARK_AREA, MIN_LANDMARK_AREA
from app.src.db import ExecutiveRole, sessionMaker, Landmark
from app.src.enums import LandmarkType
from app.src.functions import (
    checkExecutivePermission,
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
    access_token=Depends(bearer_executive),
    request_info=Depends(getRequestInfo),
):
    try:
        session = sessionMaker()
        token = getExecutiveToken(access_token.credentials, session)
        if token is None:
            raise exceptions.InvalidToken()
        role = getExecutiveRole(token, session)
        canCreateLandmark = checkExecutivePermission(
            role, ExecutiveRole.create_landmark
        )
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
async def update_landmark(access_token=Depends(bearer_executive)):
    pass


@route_executive.get("/landmark", tags=["Landmark"])
async def fetch_landmarks(access_token=Depends(bearer_executive)):
    pass


@route_executive.delete("/landmark", tags=["Landmark"])
async def delete_landmark(access_token=Depends(bearer_executive)):
    pass


## API endpoints [Operator]
@route_operator.get("/landmark", tags=["Landmark"])
async def fetch_landmarks(access_token=Depends(bearer_operator)):
    pass


## API endpoints [Vendor]
@route_vendor.get("/landmark", tags=["Landmark"])
async def fetch_landmarks(access_token=Depends(bearer_vendor)):
    pass
