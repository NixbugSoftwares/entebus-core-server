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

from app.api.bearer import bearer_executive, bearer_operator, bearer_vendor
from app.src.db import (
    Landmark,
    LandmarkInRoute,
    sessionMaker,
    Route,
)
from app.src import exceptions, validators, getters
from app.src.loggers import logEvent
from app.src.functions import enumStr, makeExceptionResponses

route_executive = APIRouter()
route_vendor = APIRouter()
route_operator = APIRouter()


## Output Schema
class LandmarkInRouteSchema(BaseModel):
    id: int
    company_id: int
    route_id: int
    landmark_id: int
    distance_from_start: int
    arrival_delta: int
    departure_delta: int
    updated_on: Optional[datetime]
    created_on: datetime


## Input Forms
class CreateForm(BaseModel):
    route_id: int = Field(Form())
    landmark_id: int = Field(Form())
    distance_from_start: int = Field(Form(gt=-1))
    arrival_delta: int = Field(Form(gt=-1))
    departure_delta: int = Field(Form(gt=-1))


class UpdateForm(BaseModel):
    id: int = Field(Form())
    distance_from_start: int | None = Field(Form(gt=-1, default=None))
    arrival_delta: int | None = Field(Form(gt=-1, default=None))
    departure_delta: int | None = Field(Form(gt=-1, default=None))


class DeleteForm(BaseModel):
    id: int = Field(Form())


## Query Parameters
class OrderIn(IntEnum):
    ASC = 1
    DESC = 2


class OrderBy(IntEnum):
    id = 1
    distance_from_start: 2
    updated_on = 3
    created_on = 4


class QueryParamsForOP(BaseModel):
    route_id: int | None = Field(Query(default=None))
    landmark_id: int | None = Field(Query(default=None))
    # id based
    id: int | None = Field(Query(default=None))
    id_ge: int | None = Field(Query(default=None))
    id_le: int | None = Field(Query(default=None))
    id_list: List[int] | None = Field(Query(default=None))
    # distance_from_start based
    distance_from_start_ge: int | None = Field(Query(default=None))
    distance_from_start_le: int | None = Field(Query(default=None))
    # arrival_delta based
    arrival_delta_ge: int | None = Field(Query(default=None))
    arrival_delta_le: int | None = Field(Query(default=None))
    # departure_delta based
    departure_delta_ge: int | None = Field(Query(default=None))
    departure_delta_le: int | None = Field(Query(default=None))
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


class QueryParams(QueryParamsForOP):
    company_id: int | None = Field(Query(default=None))


## Function
def createLandmarkInRoute(session: Session, route: Route, fParam: CreateForm):
    landmark = session.query(Landmark).filter(Landmark.id == fParam.landmark_id).first()
    if landmark is None:
        raise exceptions.InvalidValue(LandmarkInRoute.landmark_id)
    return LandmarkInRoute(
        company_id=route.company_id,
        route_id=fParam.route_id,
        landmark_id=fParam.landmark_id,
        distance_from_start=fParam.distance_from_start,
        arrival_delta=fParam.arrival_delta,
        departure_delta=fParam.departure_delta,
    )


def updateLandmarkInRoute(landmarkInRoute: LandmarkInRoute, fParam: UpdateForm):
    if (
        fParam.distance_from_start is not None
        and landmarkInRoute.distance_from_start != fParam.distance_from_start
    ):
        landmarkInRoute.distance_from_start = fParam.distance_from_start
    if (
        fParam.arrival_delta is not None
        and landmarkInRoute.arrival_delta != fParam.arrival_delta
    ):
        landmarkInRoute.arrival_delta = fParam.arrival_delta
    if (
        fParam.departure_delta is not None
        and landmarkInRoute.departure_delta != fParam.departure_delta
    ):
        landmarkInRoute.departure_delta = fParam.departure_delta


def searchLandmarkInRoute(
    session: Session, qParam: QueryParams | QueryParamsForOP
) -> List[LandmarkInRoute]:
    query = session.query(LandmarkInRoute)

    # Filters
    if qParam.company_id is not None:
        query = query.filter(LandmarkInRoute.company_id == qParam.company_id)
    if qParam.route_id is not None:
        query = query.filter(LandmarkInRoute.route_id == qParam.route_id)
    if qParam.landmark_id is not None:
        query = query.filter(LandmarkInRoute.landmark_id == qParam.landmark_id)
    # id based
    if qParam.id is not None:
        query = query.filter(LandmarkInRoute.id == qParam.id)
    if qParam.id_ge is not None:
        query = query.filter(LandmarkInRoute.id >= qParam.id_ge)
    if qParam.id_le is not None:
        query = query.filter(LandmarkInRoute.id <= qParam.id_le)
    if qParam.id_list is not None:
        query = query.filter(LandmarkInRoute.id.in_(qParam.id_list))
    # distance_from_start based
    if qParam.distance_from_start_ge is not None:
        query = query.filter(
            LandmarkInRoute.distance_from_start >= qParam.distance_from_start_ge
        )
    if qParam.distance_from_start_le is not None:
        query = query.filter(
            LandmarkInRoute.distance_from_start <= qParam.distance_from_start_le
        )
    # arrival_delta based
    if qParam.arrival_delta_ge is not None:
        query = query.filter(LandmarkInRoute.arrival_delta >= qParam.arrival_delta_ge)
    if qParam.arrival_delta_le is not None:
        query = query.filter(LandmarkInRoute.arrival_delta <= qParam.arrival_delta_le)
    # departure_delta based
    if qParam.departure_delta_ge is not None:
        query = query.filter(
            LandmarkInRoute.departure_delta >= qParam.departure_delta_ge
        )
    if qParam.departure_delta_le is not None:
        query = query.filter(
            LandmarkInRoute.departure_delta <= qParam.departure_delta_le
        )
    # updated_on based
    if qParam.updated_on_ge is not None:
        query = query.filter(LandmarkInRoute.updated_on >= qParam.updated_on_ge)
    if qParam.updated_on_le is not None:
        query = query.filter(LandmarkInRoute.updated_on <= qParam.updated_on_le)
    # created_on based
    if qParam.created_on_ge is not None:
        query = query.filter(LandmarkInRoute.created_on >= qParam.created_on_ge)
    if qParam.created_on_le is not None:
        query = query.filter(LandmarkInRoute.created_on <= qParam.created_on_le)

    # Ordering
    orderingAttribute = getattr(LandmarkInRoute, OrderBy(qParam.order_by).name)
    if qParam.order_in == OrderIn.ASC:
        query = query.order_by(orderingAttribute.asc())
    else:
        query = query.order_by(orderingAttribute.desc())

    # Pagination
    query = query.offset(qParam.offset).limit(qParam.limit)
    return query.all()


## API endpoints [Executive]
@route_executive.post(
    "/company/route/landmark",
    tags=["Landmark In Route"],
    response_model=LandmarkInRouteSchema,
    status_code=status.HTTP_201_CREATED,
    responses=makeExceptionResponses(
        [
            exceptions.InvalidToken,
            exceptions.NoPermission,
        ]
    ),
    description="""
    Create a new landmark assignment within a route for a company.  
    Requires `create_route` or `update_route` permission.  
    Validates route and landmark existence before creation.
    """,
)
async def create_landmark_in_route(
    fParam: CreateForm = Depends(),
    bearer=Depends(bearer_executive),
    request_info=Depends(getters.requestInfo),
):
    try:
        session = sessionMaker()
        token = validators.executiveToken(bearer.credentials, session)
        role = getters.executiveRole(token, session)
        if not (role.create_route | role.update_route):
            raise exceptions.NoPermission()

        route = session.query(Route).filter(Route.id == fParam.route_id).first()
        if route is None:
            raise exceptions.InvalidValue(LandmarkInRoute.route_id)
        landmarkInRoute = createLandmarkInRoute(session, route, fParam)

        session.add(landmarkInRoute)
        session.commit()
        logEvent(token, request_info, jsonable_encoder(landmarkInRoute))
        return landmarkInRoute
    except Exception as e:
        exceptions.handle(e)
    finally:
        session.close()


@route_executive.patch(
    "/company/route/landmark",
    tags=["Landmark In Route"],
    response_model=LandmarkInRouteSchema,
    responses=makeExceptionResponses(
        [
            exceptions.InvalidToken,
            exceptions.NoPermission,
            exceptions.InvalidIdentifier,
        ]
    ),
    description="""
    Update properties of a landmark within a route.  
    Requires `create_route` or `update_route` permission.  
    Only updates fields that are explicitly provided.
    """,
)
async def update_landmark_in_route(
    fParam: UpdateForm = Depends(),
    bearer=Depends(bearer_executive),
    request_info=Depends(getters.requestInfo),
):
    try:
        session = sessionMaker()
        token = validators.executiveToken(bearer.credentials, session)
        role = getters.executiveRole(token, session)
        if not (role.create_route | role.update_route):
            raise exceptions.NoPermission()

        landmarkInRoute = (
            session.query(LandmarkInRoute)
            .filter(LandmarkInRoute.id == fParam.id)
            .first()
        )
        if landmarkInRoute is None:
            raise exceptions.InvalidIdentifier()

        updateLandmarkInRoute(landmarkInRoute, fParam)
        haveUpdates = session.is_modified(landmarkInRoute)
        if haveUpdates:
            session.commit()
            session.refresh(landmarkInRoute)

        landmarkInRouteData = jsonable_encoder(landmarkInRoute)
        if haveUpdates:
            logEvent(token, request_info, landmarkInRouteData)
        return landmarkInRouteData
    except Exception as e:
        exceptions.handle(e)
    finally:
        session.close()


@route_executive.delete(
    "/company/route/landmark",
    tags=["Landmark In Route"],
    status_code=status.HTTP_204_NO_CONTENT,
    responses=makeExceptionResponses(
        [exceptions.InvalidToken, exceptions.NoPermission]
    ),
    description="""
    Delete a specific landmark assigned to a route by ID.  
    Requires `create_route` or `update_route` permission.  
    Deletes the record if it exists.
    """,
)
async def delete_landmark_in_route(
    fParam: DeleteForm = Depends(),
    bearer=Depends(bearer_executive),
    request_info=Depends(getters.requestInfo),
):
    try:
        session = sessionMaker()
        token = validators.executiveToken(bearer.credentials, session)
        role = getters.executiveRole(token, session)
        if not (role.create_route | role.update_route):
            raise exceptions.NoPermission()

        landmarkInRoute = (
            session.query(LandmarkInRoute)
            .filter(LandmarkInRoute.id == fParam.id)
            .first()
        )
        if landmarkInRoute is not None:
            session.delete(landmarkInRoute)
            session.commit()
            logEvent(token, request_info, jsonable_encoder(landmarkInRoute))
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    except Exception as e:
        exceptions.handle(e)
    finally:
        session.close()


@route_executive.get(
    "/company/route/landmark",
    tags=["Landmark In Route"],
    response_model=List[LandmarkInRouteSchema],
    responses=makeExceptionResponses([exceptions.InvalidToken]),
    description="""
    Fetch all landmarks assigned to routes.  
    Supports filtering by route ID, landmark ID, distance, delta times, etc.  
    Requires a valid executive token.
    """,
)
async def fetch_landmarks_in_route(
    qParam: QueryParams = Depends(), bearer=Depends(bearer_executive)
):
    try:
        session = sessionMaker()
        validators.executiveToken(bearer.credentials, session)

        return searchLandmarkInRoute(session, qParam)
    except Exception as e:
        exceptions.handle(e)
    finally:
        session.close()


## API endpoints [Vendor]
@route_vendor.get(
    "/company/route/landmark",
    tags=["Landmark In Route"],
    response_model=List[LandmarkInRouteSchema],
    responses=makeExceptionResponses([exceptions.InvalidToken]),
    description="""
    Fetch all landmark-in-route records viewable by vendors.  
    Supports filters like route ID, landmark ID, timing offsets, etc.  
    Requires a valid vendor token.
    """,
)
async def fetch_landmarks_in_route(
    qParam: QueryParams = Depends(), bearer=Depends(bearer_vendor)
):
    try:
        session = sessionMaker()
        validators.vendorToken(bearer.credentials, session)

        return searchLandmarkInRoute(session, qParam)
    except Exception as e:
        exceptions.handle(e)
    finally:
        session.close()


## API endpoints [Operator]
@route_operator.post(
    "/company/route/landmark",
    tags=["Landmark In Route"],
    response_model=LandmarkInRouteSchema,
    status_code=status.HTTP_201_CREATED,
    responses=makeExceptionResponses(
        [
            exceptions.InvalidToken,
            exceptions.NoPermission,
        ]
    ),
    description="""
    Create a landmark assignment within a route owned by the operator's company.  
    Requires `create_route` or `update_route` permission.  
    Validates that the route belongs to the operator's company.
    """,
)
async def create_landmark_in_route(
    fParam: CreateForm = Depends(),
    bearer=Depends(bearer_operator),
    request_info=Depends(getters.requestInfo),
):
    try:
        session = sessionMaker()
        token = validators.operatorToken(bearer.credentials, session)
        role = getters.operatorRole(token, session)
        if not (role.create_route | role.update_route):
            raise exceptions.NoPermission()

        route = (
            session.query(Route)
            .filter(Route.id == fParam.route_id)
            .filter(Route.company_id == token.company_id)
            .first()
        )
        if route is None:
            raise exceptions.InvalidValue(LandmarkInRoute.route_id)
        landmarkInRoute = createLandmarkInRoute(session, route, fParam)

        session.add(landmarkInRoute)
        session.commit()
        logEvent(token, request_info, jsonable_encoder(landmarkInRoute))
        return landmarkInRoute
    except Exception as e:
        exceptions.handle(e)
    finally:
        session.close()


@route_operator.patch(
    "/company/route/landmark",
    tags=["Landmark In Route"],
    response_model=LandmarkInRouteSchema,
    responses=makeExceptionResponses(
        [
            exceptions.InvalidToken,
            exceptions.NoPermission,
            exceptions.InvalidIdentifier,
        ]
    ),
    description="""
    Update details of a landmark in a route within the operator's company.  
    Requires `create_route` or `update_route` permission.  
    Fields not provided are ignored.
    """,
)
async def update_landmark_in_route(
    fParam: UpdateForm = Depends(),
    bearer=Depends(bearer_operator),
    request_info=Depends(getters.requestInfo),
):
    try:
        session = sessionMaker()
        token = validators.operatorToken(bearer.credentials, session)
        role = getters.operatorRole(token, session)
        if not (role.create_route | role.update_route):
            raise exceptions.NoPermission()

        landmarkInRoute = (
            session.query(LandmarkInRoute)
            .filter(LandmarkInRoute.id == fParam.id)
            .filter(LandmarkInRoute.company_id == token.company_id)
            .first()
        )
        if landmarkInRoute is None:
            raise exceptions.InvalidIdentifier()

        updateLandmarkInRoute(landmarkInRoute, fParam)
        haveUpdates = session.is_modified(landmarkInRoute)
        if haveUpdates:
            session.commit()
            session.refresh(landmarkInRoute)

        landmarkInRouteData = jsonable_encoder(landmarkInRoute)
        if haveUpdates:
            logEvent(token, request_info, landmarkInRouteData)
        return landmarkInRouteData
    except Exception as e:
        exceptions.handle(e)
    finally:
        session.close()


@route_operator.delete(
    "/company/route/landmark",
    tags=["Landmark In Route"],
    status_code=status.HTTP_204_NO_CONTENT,
    responses=makeExceptionResponses(
        [exceptions.InvalidToken, exceptions.NoPermission]
    ),
    description="""
    Delete a landmark from a route, only if it belongs to the operator's company.  
    Requires `create_route` or `update_route` permission.  
    Deletes if found and authorized.
    """,
)
async def delete_landmark_in_route(
    fParam: DeleteForm = Depends(),
    bearer=Depends(bearer_operator),
    request_info=Depends(getters.requestInfo),
):
    try:
        session = sessionMaker()
        token = validators.operatorToken(bearer.credentials, session)
        role = getters.operatorRole(token, session)
        if not (role.create_route | role.update_route):
            raise exceptions.NoPermission()

        landmarkInRoute = (
            session.query(LandmarkInRoute)
            .filter(LandmarkInRoute.id == fParam.id)
            .filter(LandmarkInRoute.company_id == token.company_id)
            .first()
        )
        if landmarkInRoute is not None:
            session.delete(landmarkInRoute)
            session.commit()
            logEvent(token, request_info, jsonable_encoder(landmarkInRoute))
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    except Exception as e:
        exceptions.handle(e)
    finally:
        session.close()


@route_operator.get(
    "/company/route/landmark",
    tags=["Landmark In Route"],
    response_model=List[LandmarkInRouteSchema],
    responses=makeExceptionResponses([exceptions.InvalidToken]),
    description="""
    Fetch all landmark-route mappings that belong to the operator's company.  
    Supports filtering by route ID, landmark ID, and time-based metrics.  
    Requires a valid operator token.
    """,
)
async def fetch_landmarks_in_route(
    qParam: QueryParamsForOP = Depends(), bearer=Depends(bearer_operator)
):
    try:
        session = sessionMaker()
        token = validators.operatorToken(bearer.credentials, session)

        qParam = QueryParams(**qParam.model_dump(), company_id=token.company_id)
        return searchLandmarkInRoute(session, qParam)
    except Exception as e:
        exceptions.handle(e)
    finally:
        session.close()
