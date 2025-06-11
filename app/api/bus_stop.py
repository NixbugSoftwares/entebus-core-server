from typing import Annotated
from fastapi import APIRouter, Depends, Form, status
from fastapi.encoders import jsonable_encoder
from shapely import Point
from sqlalchemy import func

from app.api.bearer import bearer_executive
from app.src.enums import VerificationStatus
from app.src import schemas, exceptions
from app.src.constants import (
    EPSG_3857,
    EPSG_4326,
)
from app.src.db import sessionMaker, Landmark
from app.src.functions import (
    toWKTgeometry,
    isSRID4326,
    getExecutiveRole,
    getExecutiveToken,
    getRequestInfo,
    logExecutiveEvent,
    makeExceptionResponses,
)

route_executive = APIRouter()


## API endpoints [Executive]
@route_executive.post(
    "/bus_stop",
    tags=["BusStop"],
    response_model=schemas.BusStop,
    status_code=status.HTTP_201_CREATED,
    responses=makeExceptionResponses(
        [
            exceptions.InvalidToken,
            exceptions.NoPermission,
            exceptions.InvalidWKTStringOrType,
            exceptions.InvalidSRID4326,
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
async def create_bus_stop(
    landmark_id: Annotated[int, Form()],
    name: Annotated[str, Form(max_length=128)],
    location: Annotated[str, Form(description="Accepts only SRID 4326 (WGS84)")],
    status: Annotated[
            VerificationStatus, Form()] = VerificationStatus.VALIDATING,
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
            raise exceptions.InvalidLandmarkId()
        wktBoundary = toWKTgeometry(location, Point)
        if wktBoundary is None:
            raise exceptions.InvalidWKTStringOrType()
        if not isSRID4326(wktBoundary):
            raise exceptions.InvalidSRID4326()

        location4326 = func.ST_SetSRID(func.ST_GeomFromText(location), EPSG_4326)
        withinBoundary = func.ST_Within(location4326, landmark.boundary)
        if not withinBoundary:
            raise exceptions.InvalidBusStopLocation()

        bus_stop = BusStop(name=name, landmark_id=landmark_id, status=status, location=location)
        session.add(bus_stop)
        session.commit()
        logExecutiveEvent(token, request_info, jsonable_encoder(bus_stop))
        return bus_stop
    except Exception as e:
        exceptions.handle(e)
    finally:
        session.close()
