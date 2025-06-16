from typing import Annotated, Optional
from fastapi import APIRouter, Depends, Form, status, Response
from fastapi.encoders import jsonable_encoder
from shapely import Point
from sqlalchemy import func

from app.api.bearer import bearer_executive
from app.src import schemas, exceptions
from app.src.constants import (
    EPSG_4326,
)
from app.src.db import sessionMaker, Landmark, BusStop
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
            exceptions.InvalidBusStopLocation,
            exceptions.InvalidValue(BusStop.landmark_id),
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
    name: Annotated[Optional[str], Form(max_length=128)] = None,
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
            raise exceptions.InvalidValue(BusStop.landmark_id)
        wktLocation = toWKTgeometry(location, Point)
        if wktLocation is None:
            raise exceptions.InvalidWKTStringOrType()
        if not isSRID4326(wktLocation):
            raise exceptions.InvalidSRID4326()

        name = name or landmark.name
        location4326 = func.ST_SetSRID(func.ST_GeomFromText(location), EPSG_4326)
        withinBoundary = session.scalar(func.ST_Within(location4326, landmark.boundary))
        if not withinBoundary:
            raise exceptions.InvalidBusStopLocation()

        bus_stop = BusStop(landmark_id=landmark_id, location=location, name=name)
        session.add(bus_stop)
        session.commit()
        logExecutiveEvent(token, request_info, jsonable_encoder(bus_stop))
        return bus_stop
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
            exceptions.InvalidBusStopLocation,
            exceptions.InvalidIdentifier,
        ]
    ),
    description="""
    Updates an existing bus stop with provided fields.

    - Accepts optional updates to `name`, `location` (WKT).
    - Ensures the WKT location is valid, SRID 4326, and inside the associated landmark boundary.
    - Only executives with the `update_bus_stop` permission can update bus stops.
    - Logs updates only if any field was changed.
    """,
)
async def update_bus_stop(
    id: Annotated[int, Form()],
    name: Annotated[Optional[str], Form(max_length=128)] = None,
    location: Annotated[
        Optional[str], Form(description="Accepts only SRID 4326 (WGS84)")
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

        bus_stop = session.query(BusStop).filter(BusStop.id == id).first()
        if bus_stop is None:
            raise exceptions.InvalidIdentifier()
        if name is not None and bus_stop.name != name:
            bus_stop.name = name

        if location is not None:
            wktLocation = toWKTgeometry(location, Point)
            if wktLocation is None:
                raise exceptions.InvalidWKTStringOrType()
            if not isSRID4326(wktLocation):
                raise exceptions.InvalidSRID4326()
            landmark = (
                session.query(Landmark)
                .filter(Landmark.id == bus_stop.landmark_id)
                .first()
            )
            location4326 = func.ST_SetSRID(func.ST_GeomFromText(location), EPSG_4326)
            withinBoundary = session.scalar(
                func.ST_Within(location4326, landmark.boundary)
            )
            if not withinBoundary:
                raise exceptions.InvalidBusStopLocation()
            bus_stop.location = location4326

        if session.is_modified(bus_stop):
            session.commit()
            session.refresh(bus_stop)

            logData = jsonable_encoder(bus_stop, exclude={"location"})
            logData["location"] = session.scalar(func.ST_AsText(bus_stop.location))
            logExecutiveEvent(token, request_info, logData)
            return logData

        else:
            busStop = jsonable_encoder(bus_stop, exclude={"location"})
            busStop["location"] = session.scalar(func.ST_AsText(bus_stop.location))
            session.expunge(bus_stop)
            return busStop
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

        bus_stop = session.query(BusStop).filter(BusStop.id == id).first()
        if bus_stop:
            logData = jsonable_encoder(bus_stop, exclude={"location"})
            logData["location"] = session.scalar(func.ST_AsText(bus_stop.location))
            session.delete(bus_stop)
            session.commit()
            logExecutiveEvent(token, request_info, logData)
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    except Exception as e:
        exceptions.handle(e)
    finally:
        session.close()
