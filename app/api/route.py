from datetime import datetime, time
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
from app.src.db import ExecutiveRole, OperatorRole, sessionMaker, Route
from app.src import exceptions, validators, getters
from app.src.loggers import logEvent
from app.src.functions import enumStr, makeExceptionResponses

route_executive = APIRouter()
route_vendor = APIRouter()
route_operator = APIRouter()


## Output Schema
class RouteSchema(BaseModel):
    id: int
    company_id: int
    name: str
    start_time: time
    updated_on: Optional[datetime]
    created_on: datetime


## Input Forms
class CreateFormForOP(BaseModel):
    name: str = Field(Form(max_length=4096))
    start_time: time = Field(Form())


class CreateFormForEX(CreateFormForOP):
    company_id: int = Field(Form())


class UpdateForm(BaseModel):
    id: int = Field(Form())
    name: str | None = Field(Form(max_length=4096, default=None))
    start_time: time | None = Field(Form(default=None))


class DeleteForm(BaseModel):
    id: int = Field(Form())


## Query Parameters
class OrderIn(IntEnum):
    ASC = 1
    DESC = 2


class OrderBy(IntEnum):
    id = 1
    updated_on = 2
    created_on = 3


class QueryParamsForOP(BaseModel):
    name: str | None = Field(Query(default=None))
    start_time: time | None = Field(Query(default=None))
    # id based
    id: int | None = Field(Query(default=None))
    id_ge: int | None = Field(Query(default=None))
    id_le: int | None = Field(Query(default=None))
    id_list: List[int] | None = Field(Query(default=None))
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
def updateRoute(route: Route, fParam: UpdateForm):
    if fParam.name is not None and route.name != fParam.name:
        route.name = fParam.name
    if fParam.start_time is not None and route.start_time != fParam.start_time:
        route.start_time = fParam.start_time


def searchRoute(
    session: Session, qParam: QueryParams | QueryParamsForOP
) -> List[Route]:
    query = session.query(Route)

    # Filters
    if qParam.company_id is not None:
        query = query.filter(Route.company_id == qParam.company_id)
    if qParam.name is not None:
        query = query.filter(Route.name.ilike(f"%{qParam.name}%"))
    if qParam.start_time is not None:
        query = query.filter(Route.start_time == qParam.start_time)
    # id based
    if qParam.id is not None:
        query = query.filter(Route.id == qParam.id)
    if qParam.id_ge is not None:
        query = query.filter(Route.id >= qParam.id_ge)
    if qParam.id_le is not None:
        query = query.filter(Route.id <= qParam.id_le)
    if qParam.id_list is not None:
        query = query.filter(Route.id.in_(qParam.id_list))
    # updated_on based
    if qParam.updated_on_ge is not None:
        query = query.filter(Route.updated_on >= qParam.updated_on_ge)
    if qParam.updated_on_le is not None:
        query = query.filter(Route.updated_on <= qParam.updated_on_le)
    # created_on based
    if qParam.created_on_ge is not None:
        query = query.filter(Route.created_on >= qParam.created_on_ge)
    if qParam.created_on_le is not None:
        query = query.filter(Route.created_on <= qParam.created_on_le)

    # Ordering
    orderingAttribute = getattr(Route, OrderBy(qParam.order_by).name)
    if qParam.order_in == OrderIn.ASC:
        query = query.order_by(orderingAttribute.asc())
    else:
        query = query.order_by(orderingAttribute.desc())

    # Pagination
    query = query.offset(qParam.offset).limit(qParam.limit)
    return query.all()


## API endpoints [Executive]
@route_executive.post(
    "/company/route",
    tags=["Route"],
    response_model=RouteSchema,
    status_code=status.HTTP_201_CREATED,
    responses=makeExceptionResponses(
        [
            exceptions.InvalidToken,
            exceptions.NoPermission,
        ]
    ),
    description="""
    Creates a new route for a specified company.

    - Only executives with `create_route` permission can create routes.
    - Logs the route creation activity with the associated token.
    - Requires a valid company ID, route name, and start time.
    - Ensures the route is correctly associated with the specified company.
    """,
)
async def create_route(
    fParam: CreateFormForEX = Depends(),
    bearer=Depends(bearer_executive),
    request_info=Depends(getters.requestInfo),
):
    try:
        session = sessionMaker()
        token = validators.executiveToken(bearer.credentials, session)
        role = getters.executiveRole(token, session)
        validators.executivePermission(role, ExecutiveRole.create_route)

        route = Route(
            company_id=fParam.company_id, name=fParam.name, start_time=fParam.start_time
        )
        session.add(route)
        session.commit()
        logEvent(token, request_info, jsonable_encoder(route))
        return route
    except Exception as e:
        exceptions.handle(e)
    finally:
        session.close()


@route_executive.patch(
    "/company/route",
    tags=["Route"],
    response_model=RouteSchema,
    responses=makeExceptionResponses(
        [
            exceptions.InvalidToken,
            exceptions.NoPermission,
            exceptions.InvalidIdentifier,
        ]
    ),
    description="""
    Updates an existing route belonging to any company.

    - Only executives with `update_route` permission can perform this operation.
    - Validates the route ID before applying updates.
    - Supports partial updates such as modifying the route name or start time.
    - Changes are saved only if the route data has been modified.
    - Logs the route updating activity with the associated token.
    """,
)
async def update_route(
    fParam: UpdateForm = Depends(),
    bearer=Depends(bearer_executive),
    request_info=Depends(getters.requestInfo),
):
    try:
        session = sessionMaker()
        token = validators.executiveToken(bearer.credentials, session)
        role = getters.executiveRole(token, session)
        validators.executivePermission(role, ExecutiveRole.update_route)

        route = session.query(Route).filter(Route.id == fParam.id).first()
        if route is None:
            raise exceptions.InvalidIdentifier()

        updateRoute(route, fParam)
        haveUpdates = session.is_modified(route)
        if haveUpdates:
            session.commit()
            session.refresh(route)

        routeData = jsonable_encoder(route)
        if haveUpdates:
            logEvent(token, request_info, routeData)
        return routeData
    except Exception as e:
        exceptions.handle(e)
    finally:
        session.close()


@route_executive.delete(
    "/company/route",
    tags=["Route"],
    status_code=status.HTTP_204_NO_CONTENT,
    responses=makeExceptionResponses(
        [exceptions.InvalidToken, exceptions.NoPermission]
    ),
    description="""
    Deletes an existing route from any company.

    - Only executives with `delete_route` permission can perform this operation.
    - Validates the route ID before deletion.
    - If the route exists, it is permanently removed from the system.
    - Logs the deletion activity using the executive's token and request metadata.
    - Returns HTTP 204 status code upon successful deletion.
    """,
)
async def delete_route(
    fParam: DeleteForm = Depends(),
    bearer=Depends(bearer_executive),
    request_info=Depends(getters.requestInfo),
):
    try:
        session = sessionMaker()
        token = validators.executiveToken(bearer.credentials, session)
        role = getters.executiveRole(token, session)
        validators.executivePermission(role, ExecutiveRole.delete_route)

        route = session.query(Route).filter(Route.id == fParam.id).first()
        if route is not None:
            session.delete(route)
            session.commit()
            logEvent(token, request_info, jsonable_encoder(route))
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    except Exception as e:
        exceptions.handle(e)
    finally:
        session.close()


@route_executive.get(
    "/company/route",
    tags=["Route"],
    response_model=List[RouteSchema],
    responses=makeExceptionResponses([exceptions.InvalidToken]),
    description="""
    Fetches a list of routes across companies based on provided query parameters.

    - Requires a valid executive token for authentication.
    - Allows unrestricted access to routes across multiple companies.
    - Supports query parameters for filtering routes by ID, name, company ID, start time, and more.
    - Returns all matching routes based on the provided filters.
    """,
)
async def fetch_routes(
    qParam: QueryParams = Depends(), bearer=Depends(bearer_executive)
):
    try:
        session = sessionMaker()
        validators.executiveToken(bearer.credentials, session)

        return searchRoute(session, qParam)
    except Exception as e:
        exceptions.handle(e)
    finally:
        session.close()


## API endpoints [Vendor]
@route_vendor.get(
    "/company/route",
    tags=["Route"],
    response_model=List[RouteSchema],
    responses=makeExceptionResponses([exceptions.InvalidToken]),
    description="""
    Fetches a list of routes across companies based on provided query parameters.

    - Requires a valid vendor token for authentication.
    - Supports flexible filtering using query parameters such as route ID, name, company ID, or start time.
    - Returns all matching routes without restricting to a specific company.
    - Enables vendors to access route data for authorized purposes.
    """,
)
async def fetch_tokens(qParam: QueryParams = Depends(), bearer=Depends(bearer_vendor)):
    try:
        session = sessionMaker()
        validators.vendorToken(bearer.credentials, session)

        return searchRoute(session, qParam)
    except Exception as e:
        exceptions.handle(e)
    finally:
        session.close()


## API endpoints [Operator]
@route_operator.post(
    "/company/route",
    tags=["Route"],
    response_model=RouteSchema,
    status_code=status.HTTP_201_CREATED,
    responses=makeExceptionResponses(
        [
            exceptions.InvalidToken,
            exceptions.NoPermission,
        ]
    ),
    description="""
    Creates a new route under the operator's associated company.

    - Only operators with `create_route` permission can create routes.
    - Logs the route creation activity with the associated token and request metadata.
    - The route must include a valid name and a defined start time.
    - Automatically assigns the route to the company derived from the authenticated token.
    """,
)
async def create_route(
    fParam: CreateFormForOP = Depends(),
    bearer=Depends(bearer_operator),
    request_info=Depends(getters.requestInfo),
):
    try:
        session = sessionMaker()
        token = validators.operatorToken(bearer.credentials, session)
        role = getters.operatorRole(token, session)
        validators.operatorPermission(role, OperatorRole.create_route)

        route = Route(
            company_id=token.company_id, name=fParam.name, start_time=fParam.start_time
        )
        session.add(route)
        session.commit()
        logEvent(token, request_info, jsonable_encoder(route))
        return route
    except Exception as e:
        exceptions.handle(e)
    finally:
        session.close()


@route_operator.patch(
    "/company/route",
    tags=["Route"],
    response_model=RouteSchema,
    responses=makeExceptionResponses(
        [
            exceptions.InvalidToken,
            exceptions.NoPermission,
            exceptions.InvalidIdentifier,
        ]
    ),
    description="""
    Updates an existing route belonging to the operator's associated company.

    - Only operators with `update_route` permission can update routes.
    - Validates route ID and ensures it belongs to the same company as the operator.
    - Applies partial updates such as name or start time using the provided form data.
    - Logs the update activity only if changes are detected.
    """,
)
async def update_route(
    fParam: UpdateForm = Depends(),
    bearer=Depends(bearer_operator),
    request_info=Depends(getters.requestInfo),
):
    try:
        session = sessionMaker()
        token = validators.operatorToken(bearer.credentials, session)
        role = getters.operatorRole(token, session)
        validators.operatorPermission(role, OperatorRole.update_route)

        route = (
            session.query(Route)
            .filter(Route.id == fParam.id)
            .filter(Route.company_id == token.company_id)
            .first()
        )
        if route is None:
            raise exceptions.InvalidIdentifier()

        updateRoute(route, fParam)
        haveUpdates = session.is_modified(route)
        if haveUpdates:
            session.commit()
            session.refresh(route)

        routeData = jsonable_encoder(route)
        if haveUpdates:
            logEvent(token, request_info, routeData)
        return routeData
    except Exception as e:
        exceptions.handle(e)
    finally:
        session.close()


@route_operator.delete(
    "/company/route",
    tags=["Route"],
    status_code=status.HTTP_204_NO_CONTENT,
    responses=makeExceptionResponses(
        [exceptions.InvalidToken, exceptions.NoPermission]
    ),
    description="""
    Deletes an existing route belonging to the operator's associated company.

    - Only operators with `delete_route` permission can delete routes.
    - Validates the route ID and ensures it belongs to the operator's company.
    - If the route exists, it is permanently removed from the system.
    - Logs the deletion activity using the operator's token and request metadata.
    - Returns HTTP 204 status code upon successful deletion.
    """,
)
async def delete_route(
    fParam: DeleteForm = Depends(),
    bearer=Depends(bearer_operator),
    request_info=Depends(getters.requestInfo),
):
    try:
        session = sessionMaker()
        token = validators.operatorToken(bearer.credentials, session)
        role = getters.operatorRole(token, session)
        validators.operatorPermission(role, OperatorRole.delete_route)

        route = (
            session.query(Route)
            .filter(Route.id == fParam.id)
            .filter(Route.company_id == token.company_id)
            .first()
        )

        if route is not None:
            session.delete(route)
            session.commit()
            logEvent(token, request_info, jsonable_encoder(route))
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    except Exception as e:
        exceptions.handle(e)
    finally:
        session.close()


@route_operator.get(
    "/company/route",
    tags=["Route"],
    response_model=List[RouteSchema],
    responses=makeExceptionResponses([exceptions.InvalidToken]),
    description="""
    Fetches a list of routes belonging to the operator's associated company.

    - Requires a valid operator token for authentication.
    - Supports query parameters for filtering routes.
    - Returns only routes belonging to the operator's company.
    - Provides a list of matching routes based on the applied filters.
    """,
)
async def fetch_routes(
    qParam: QueryParamsForOP = Depends(), bearer=Depends(bearer_operator)
):
    try:
        session = sessionMaker()
        token = validators.operatorToken(bearer.credentials, session)

        qParam = QueryParams(**qParam.model_dump(), company_id=token.company_id)
        return searchRoute(session, qParam)
    except Exception as e:
        exceptions.handle(e)
    finally:
        session.close()
