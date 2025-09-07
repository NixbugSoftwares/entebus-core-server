from datetime import datetime, time
from enum import IntEnum
from typing import List, Optional
from fastapi import APIRouter, Depends, Query, Response, status, Form
from sqlalchemy.orm.session import Session
from fastapi.encoders import jsonable_encoder
from pydantic import BaseModel, Field

from app.api.bearer import bearer_executive, bearer_operator, bearer_vendor
from app.src.db import ExecutiveRole, OperatorRole, sessionMaker, Route
from app.src import exceptions, validators, getters
from app.src.loggers import logEvent
from app.src.redis import acquireLock, releaseLock
from app.src.functions import (
    enumStr,
    fuseExceptionResponses,
    updateIfChanged,
    promoteToParent,
)

route_executive = APIRouter()
route_vendor = APIRouter()
route_operator = APIRouter()
from app.src.urls import URL_ROUTE


## Output Schema
class RouteSchema(BaseModel):
    id: int
    company_id: int
    name: str
    start_time: time
    status: int
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
    start_time = 4


class QueryParamsForOP(BaseModel):
    name: str | None = Field(Query(default=None))
    status: int | None = Field(Query(default=None))
    # id based
    id: int | None = Field(Query(default=None))
    id_ge: int | None = Field(Query(default=None))
    id_le: int | None = Field(Query(default=None))
    id_list: List[int] | None = Field(Query(default=None))
    # start_time based
    start_time_ge: time | None = Field(Query(default=None))
    start_time_le: time | None = Field(Query(default=None))
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
    updateIfChanged(route, fParam, [Route.name.key, Route.start_time.key])


def searchRoute(
    session: Session, qParam: QueryParams | QueryParamsForOP
) -> List[Route]:
    query = session.query(Route)

    # Filters
    if qParam.company_id is not None:
        query = query.filter(Route.company_id == qParam.company_id)
    if qParam.name is not None:
        query = query.filter(Route.name.ilike(f"%{qParam.name}%"))
    if qParam.status is not None:
        query = query.filter(Route.status == qParam.status)
    # id based
    if qParam.id is not None:
        query = query.filter(Route.id == qParam.id)
    if qParam.id_ge is not None:
        query = query.filter(Route.id >= qParam.id_ge)
    if qParam.id_le is not None:
        query = query.filter(Route.id <= qParam.id_le)
    if qParam.id_list is not None:
        query = query.filter(Route.id.in_(qParam.id_list))
    # start_time based
    if qParam.start_time_ge is not None:
        query = query.filter(Route.start_time >= qParam.start_time_ge)
    if qParam.start_time_le is not None:
        query = query.filter(Route.start_time <= qParam.start_time_le)
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
    URL_ROUTE,
    tags=["Route"],
    response_model=RouteSchema,
    status_code=status.HTTP_201_CREATED,
    responses=fuseExceptionResponses(
        [exceptions.InvalidToken(), exceptions.NoPermission()]
    ),
    description="""
    Create a new route for a specified company.  
    Requires executive role with `create_route` permission.  
    By default the status of the route is INVALID.      
    Accepts route name and start time.
    """,
)
async def create_route(
    fParam: CreateFormForEX = Depends(),
    bearer=Depends(bearer_executive),
    request_info=Depends(getters.requestInfo),
):
    try:
        session = sessionMaker()
        token = validators.executive_token(bearer.credentials, session)
        role = getters.executiveRole(token, session)
        validators.executive_permission(role, ExecutiveRole.create_route)

        route = Route(
            company_id=fParam.company_id, name=fParam.name, start_time=fParam.start_time
        )
        session.add(route)
        session.commit()
        session.refresh(route)

        routeData = jsonable_encoder(route)
        logEvent(token, request_info, routeData)
        return routeData
    except Exception as e:
        exceptions.handle(e)
    finally:
        session.close()


@route_executive.patch(
    URL_ROUTE,
    tags=["Route"],
    response_model=RouteSchema,
    responses=fuseExceptionResponses(
        [
            exceptions.InvalidToken(),
            exceptions.NoPermission(),
            exceptions.InvalidIdentifier(),
        ]
    ),
    description="""
    Update an existing route by ID.  
    Requires executive role with `update_route` permission.  
    Only provided fields (name, start_time) will be updated.
    """,
)
async def update_route(
    fParam: UpdateForm = Depends(),
    bearer=Depends(bearer_executive),
    request_info=Depends(getters.requestInfo),
):
    try:
        session = sessionMaker()
        token = validators.executive_token(bearer.credentials, session)
        role = getters.executiveRole(token, session)
        validators.executive_permission(role, ExecutiveRole.update_route)

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
    URL_ROUTE,
    tags=["Route"],
    status_code=status.HTTP_204_NO_CONTENT,
    responses=fuseExceptionResponses(
        [
            exceptions.InvalidToken(),
            exceptions.NoPermission(),
            exceptions.LockAcquireTimeout(),
        ]
    ),
    description="""
    Delete an existing route by ID.  
    Requires executive role with `delete_route` permission.  
    Deletes the route if it exists and logs the action.
    """,
)
async def delete_route(
    fParam: DeleteForm = Depends(),
    bearer=Depends(bearer_executive),
    request_info=Depends(getters.requestInfo),
):
    routeLock = None
    try:
        session = sessionMaker()
        token = validators.executive_token(bearer.credentials, session)
        role = getters.executiveRole(token, session)
        validators.executive_permission(role, ExecutiveRole.delete_route)

        routeLock = acquireLock(Route.__tablename__, fParam.id)
        route = session.query(Route).filter(Route.id == fParam.id).first()
        if route is None:
            releaseLock(routeLock)
        if route is not None:
            session.delete(route)
            session.commit()
            logEvent(token, request_info, jsonable_encoder(route))
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    except Exception as e:
        exceptions.handle(e)
    finally:
        releaseLock(routeLock)
        session.close()


@route_executive.get(
    URL_ROUTE,
    tags=["Route"],
    response_model=List[RouteSchema],
    responses=fuseExceptionResponses([exceptions.InvalidToken()]),
    description="""
    Fetch a list of all routes across companies.  
    Supports filtering by company ID, name, time, and metadata.  
    Requires a valid executive token.
    """,
)
async def fetch_route(
    qParam: QueryParams = Depends(), bearer=Depends(bearer_executive)
):
    try:
        session = sessionMaker()
        validators.executive_token(bearer.credentials, session)

        return searchRoute(session, qParam)
    except Exception as e:
        exceptions.handle(e)
    finally:
        session.close()


## API endpoints [Vendor]
@route_vendor.get(
    URL_ROUTE,
    tags=["Route"],
    response_model=List[RouteSchema],
    responses=fuseExceptionResponses([exceptions.InvalidToken()]),
    description="""
    Fetch a list of all routes across companies.  
    Only available to users with a valid vendor token.  
    Supports filtering, sorting, and pagination.
    """,
)
async def fetch_route(qParam: QueryParams = Depends(), bearer=Depends(bearer_vendor)):
    try:
        session = sessionMaker()
        validators.vendor_token(bearer.credentials, session)

        return searchRoute(session, qParam)
    except Exception as e:
        exceptions.handle(e)
    finally:
        session.close()


## API endpoints [Operator]
@route_operator.post(
    URL_ROUTE,
    tags=["Route"],
    response_model=RouteSchema,
    status_code=status.HTTP_201_CREATED,
    responses=fuseExceptionResponses(
        [exceptions.InvalidToken(), exceptions.NoPermission()]
    ),
    description="""
    Create a new route for the operator's own company.  
    Requires operator role with `create_route` permission.  
    By default the status of the route is INVALID.  
    The company ID is derived from the token, not user input.
    """,
)
async def create_route(
    fParam: CreateFormForOP = Depends(),
    bearer=Depends(bearer_operator),
    request_info=Depends(getters.requestInfo),
):
    try:
        session = sessionMaker()
        token = validators.operator_token(bearer.credentials, session)
        role = getters.operatorRole(token, session)
        validators.operator_permission(role, OperatorRole.create_route)

        route = Route(
            company_id=token.company_id, name=fParam.name, start_time=fParam.start_time
        )
        session.add(route)
        session.commit()
        session.refresh(route)

        routeData = jsonable_encoder(route)
        logEvent(token, request_info, routeData)
        return routeData
    except Exception as e:
        exceptions.handle(e)
    finally:
        session.close()


@route_operator.patch(
    URL_ROUTE,
    tags=["Route"],
    response_model=RouteSchema,
    responses=fuseExceptionResponses(
        [
            exceptions.InvalidToken(),
            exceptions.NoPermission(),
            exceptions.InvalidIdentifier(),
        ]
    ),
    description="""
    Update an existing route belonging to the operator's company.  
    Requires operator role with `update_route` permission.  
    Ensures the route is owned by the operator's company.
    """,
)
async def update_route(
    fParam: UpdateForm = Depends(),
    bearer=Depends(bearer_operator),
    request_info=Depends(getters.requestInfo),
):
    try:
        session = sessionMaker()
        token = validators.operator_token(bearer.credentials, session)
        role = getters.operatorRole(token, session)
        validators.operator_permission(role, OperatorRole.update_route)

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
    URL_ROUTE,
    tags=["Route"],
    status_code=status.HTTP_204_NO_CONTENT,
    responses=fuseExceptionResponses(
        [
            exceptions.InvalidToken(),
            exceptions.NoPermission(),
            exceptions.LockAcquireTimeout(),
        ]
    ),
    description="""
    Delete a route belonging to the operator's company.  
    Requires operator role with `delete_route` permission.  
    Only routes owned by the operator's company can be deleted.
    """,
)
async def delete_route(
    fParam: DeleteForm = Depends(),
    bearer=Depends(bearer_operator),
    request_info=Depends(getters.requestInfo),
):
    routeLock = None
    try:
        session = sessionMaker()
        token = validators.operator_token(bearer.credentials, session)
        role = getters.operatorRole(token, session)
        validators.operator_permission(role, OperatorRole.delete_route)

        routeLock = acquireLock(Route.__tablename__, fParam.id)
        route = (
            session.query(Route)
            .filter(Route.id == fParam.id)
            .filter(Route.company_id == token.company_id)
            .first()
        )
        if route is None:
            releaseLock(routeLock)
        if route is not None:
            session.delete(route)
            session.commit()
            logEvent(token, request_info, jsonable_encoder(route))
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    except Exception as e:
        exceptions.handle(e)
    finally:
        releaseLock(routeLock)
        session.close()


@route_operator.get(
    URL_ROUTE,
    tags=["Route"],
    response_model=List[RouteSchema],
    responses=fuseExceptionResponses([exceptions.InvalidToken()]),
    description="""
    Fetch a list of routes belonging to the operator's own company.  
    Supports filters like ID, time, name, and creation timestamps.  
    Requires a valid operator token.
    """,
)
async def fetch_route(
    qParam: QueryParamsForOP = Depends(), bearer=Depends(bearer_operator)
):
    try:
        session = sessionMaker()
        token = validators.operator_token(bearer.credentials, session)

        qParam = promoteToParent(qParam, QueryParams, company_id=token.company_id)
        return searchRoute(session, qParam)
    except Exception as e:
        exceptions.handle(e)
    finally:
        session.close()
