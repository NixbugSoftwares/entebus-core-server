from datetime import datetime
from enum import IntEnum
from typing import List, Optional
from fastapi import APIRouter, Depends, Query, Response, status, Form
from fastapi.encoders import jsonable_encoder
from pydantic import BaseModel, Field
from sqlalchemy.orm.session import Session

from app.api.bearer import bearer_executive, bearer_operator
from app.src.db import OperatorRole, ExecutiveRole, sessionMaker
from app.src import exceptions, validators, getters
from app.src.loggers import logEvent
from app.src.functions import enumStr, makeExceptionResponses

route_executive = APIRouter()
route_operator = APIRouter()


## Output Schema
class OperatorRoleSchema(BaseModel):
    id: int
    name: str
    company_id: int
    manage_token: bool
    update_company: bool
    create_operator: bool
    update_operator: bool
    delete_operator: bool
    create_route: bool
    update_route: bool
    delete_route: bool
    create_bus: bool
    update_bus: bool
    delete_bus: bool
    create_schedule: bool
    update_schedule: bool
    delete_schedule: bool
    create_service: bool
    update_service: bool
    delete_service: bool
    create_fare: bool
    update_fare: bool
    delete_fare: bool
    create_duty: bool
    update_duty: bool
    delete_duty: bool
    create_role: bool
    update_role: bool
    delete_role: bool
    updated_on: Optional[datetime]
    created_on: datetime


class CreateFormForOP(BaseModel):
    name: str = Field(Form(max_length=32))
    manage_token: bool = Field(Form(default=False))
    update_company: bool = Field(Form(default=False))
    create_operator: bool = Field(Form(default=False))
    update_operator: bool = Field(Form(default=False))
    delete_operator: bool = Field(Form(default=False))
    create_route: bool = Field(Form(default=False))
    update_route: bool = Field(Form(default=False))
    delete_route: bool = Field(Form(default=False))
    create_bus: bool = Field(Form(default=False))
    update_bus: bool = Field(Form(default=False))
    delete_bus: bool = Field(Form(default=False))
    create_schedule: bool = Field(Form(default=False))
    update_schedule: bool = Field(Form(default=False))
    delete_schedule: bool = Field(Form(default=False))
    create_service: bool = Field(Form(default=False))
    update_service: bool = Field(Form(default=False))
    delete_service: bool = Field(Form(default=False))
    create_fare: bool = Field(Form(default=False))
    update_fare: bool = Field(Form(default=False))
    delete_fare: bool = Field(Form(default=False))
    create_duty: bool = Field(Form(default=False))
    update_duty: bool = Field(Form(default=False))
    delete_duty: bool = Field(Form(default=False))
    create_role: bool = Field(Form(default=False))
    update_role: bool = Field(Form(default=False))
    delete_role: bool = Field(Form(default=False))


class CreateFormForEX(CreateFormForOP):
    company_id: int = Field(Form())


class UpdateForm(BaseModel):
    id: int = Field(Form())
    name: str | None = Field(Form(max_length=32, default=None))
    manage_token: bool | None = Field(Form(default=None))
    update_company: bool | None = Field(Form(default=None))
    create_operator: bool | None = Field(Form(default=None))
    update_operator: bool | None = Field(Form(default=None))
    delete_operator: bool | None = Field(Form(default=None))
    create_route: bool | None = Field(Form(default=None))
    update_route: bool | None = Field(Form(default=None))
    delete_route: bool | None = Field(Form(default=None))
    create_bus: bool | None = Field(Form(default=None))
    update_bus: bool | None = Field(Form(default=None))
    delete_bus: bool | None = Field(Form(default=None))
    create_schedule: bool | None = Field(Form(default=None))
    update_schedule: bool | None = Field(Form(default=None))
    delete_schedule: bool | None = Field(Form(default=None))
    create_service: bool | None = Field(Form(default=None))
    update_service: bool | None = Field(Form(default=None))
    delete_service: bool | None = Field(Form(default=None))
    create_fare: bool | None = Field(Form(default=None))
    update_fare: bool | None = Field(Form(default=None))
    delete_fare: bool | None = Field(Form(default=None))
    create_duty: bool | None = Field(Form(default=None))
    update_duty: bool | None = Field(Form(default=None))
    delete_duty: bool | None = Field(Form(default=None))
    create_role: bool | None = Field(Form(default=None))
    update_role: bool | None = Field(Form(default=None))
    delete_role: bool | None = Field(Form(default=None))


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
    # id based
    id: int | None = Field(Query(default=None))
    id_ge: int | None = Field(Query(default=None))
    id_le: int | None = Field(Query(default=None))
    id_list: List[int] | None = Field(Query(default=None))
    # Token management permissions based
    manage_token: bool | None = Field(Query(default=None))
    # Company management permissions based
    update_company: bool | None = Field(Query(default=None))
    # Operator management permissions based
    create_operator: bool | None = Field(Query(default=None))
    update_operator: bool | None = Field(Query(default=None))
    delete_operator: bool | None = Field(Query(default=None))
    # Route management permissions based
    create_route: bool | None = Field(Query(default=None))
    update_route: bool | None = Field(Query(default=None))
    delete_route: bool | None = Field(Query(default=None))
    # Bus management permissions based
    create_bus: bool | None = Field(Query(default=None))
    update_bus: bool | None = Field(Query(default=None))
    delete_bus: bool | None = Field(Query(default=None))
    # Schedule management permissions based
    create_schedule: bool | None = Field(Query(default=None))
    update_schedule: bool | None = Field(Query(default=None))
    delete_schedule: bool | None = Field(Query(default=None))
    # Service management permissions based
    create_service: bool | None = Field(Query(default=None))
    update_service: bool | None = Field(Query(default=None))
    delete_service: bool | None = Field(Query(default=None))
    # Fare management permissions based
    create_fare: bool | None = Field(Query(default=None))
    update_fare: bool | None = Field(Query(default=None))
    delete_fare: bool | None = Field(Query(default=None))
    # Duty management permissions based
    create_duty: bool | None = Field(Query(default=None))
    update_duty: bool | None = Field(Query(default=None))
    delete_duty: bool | None = Field(Query(default=None))
    # Executive role management permissions based
    create_role: bool | None = Field(Query(default=None))
    update_role: bool | None = Field(Query(default=None))
    delete_role: bool | None = Field(Query(default=None))
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


class QueryParamsForEX(QueryParamsForOP):
    company_id: int | None = Field(Query(default=None))


## Functions
def updateRole(role: OperatorRole, fParam: UpdateForm):
    if fParam.name is not None and role.name != fParam.name:
        role.name = fParam.name
    if fParam.manage_token is not None and role.manage_token != fParam.manage_token:
        role.manage_token = fParam.manage_token
    if (
        fParam.update_company is not None
        and role.update_company != fParam.update_company
    ):
        role.update_company = fParam.update_company
    if (
        fParam.create_operator is not None
        and role.create_operator != fParam.create_operator
    ):
        role.create_operator = fParam.create_operator
    if (
        fParam.update_operator is not None
        and role.update_operator != fParam.update_operator
    ):
        role.update_operator = fParam.update_operator
    if (
        fParam.delete_operator is not None
        and role.delete_operator != fParam.delete_operator
    ):
        role.delete_operator = fParam.delete_operator
    if fParam.create_route is not None and role.create_route != fParam.create_route:
        role.create_route = fParam.create_route
    if fParam.update_route is not None and role.update_route != fParam.update_route:
        role.update_route = fParam.update_route
    if fParam.delete_route is not None and role.delete_route != fParam.delete_route:
        role.delete_route = fParam.delete_route
    if fParam.create_bus is not None and role.create_bus != fParam.create_bus:
        role.create_bus = fParam.create_bus
    if fParam.update_bus is not None and role.update_bus != fParam.update_bus:
        role.update_bus = fParam.update_bus
    if fParam.delete_bus is not None and role.delete_bus != fParam.delete_bus:
        role.delete_bus = fParam.delete_bus
    if (
        fParam.create_schedule is not None
        and role.create_schedule != fParam.create_schedule
    ):
        role.create_schedule = fParam.create_schedule
    if (
        fParam.update_schedule is not None
        and role.update_schedule != fParam.update_schedule
    ):
        role.update_schedule = fParam.update_schedule
    if (
        fParam.delete_schedule is not None
        and role.delete_schedule != fParam.delete_schedule
    ):
        role.delete_schedule = fParam.delete_schedule
    if (
        fParam.create_service is not None
        and role.create_service != fParam.create_service
    ):
        role.create_service = fParam.create_service
    if (
        fParam.update_service is not None
        and role.update_service != fParam.update_service
    ):
        role.update_service = fParam.update_service
    if (
        fParam.delete_service is not None
        and role.delete_service != fParam.delete_service
    ):
        role.delete_service = fParam.delete_service
    if fParam.create_fare is not None and role.create_fare != fParam.create_fare:
        role.create_fare = fParam.create_fare
    if fParam.update_fare is not None and role.update_fare != fParam.update_fare:
        role.update_fare = fParam.update_fare
    if fParam.delete_fare is not None and role.delete_fare != fParam.delete_fare:
        role.delete_fare = fParam.delete_fare
    if fParam.create_duty is not None and role.create_duty != fParam.create_duty:
        role.create_duty = fParam.create_duty
    if fParam.update_duty is not None and role.update_duty != fParam.update_duty:
        role.update_duty = fParam.update_duty
    if fParam.delete_duty is not None and role.delete_duty != fParam.delete_duty:
        role.delete_duty = fParam.delete_duty
    if fParam.create_role is not None and role.create_role != fParam.create_role:
        role.create_role = fParam.create_role
    if fParam.update_role is not None and role.update_role != fParam.update_role:
        role.update_role = fParam.update_role
    if fParam.delete_role is not None and role.delete_role != fParam.delete_role:
        role.delete_role = fParam.delete_role


def searchRole(
    session: Session, qParam: QueryParamsForOP | QueryParamsForEX
) -> List[OperatorRole]:
    query = session.query(OperatorRole)

    if qParam.name is not None:
        query = query.filter(OperatorRole.name.like(f"%{qParam.name}%"))
    if qParam.company_id is not None:
        query = query.filter(OperatorRole.company_id == qParam.company_id)
    # id based
    if qParam.id is not None:
        query = query.filter(OperatorRole.id == qParam.id)
    if qParam.id_ge is not None:
        query = query.filter(OperatorRole.id >= qParam.id_ge)
    if qParam.id_le is not None:
        query = query.filter(OperatorRole.id <= qParam.id_le)
    if qParam.id_list is not None:
        query = query.filter(OperatorRole.id.in_(qParam.id_list))
    # Token management permissions
    if qParam.manage_token is not None:
        query = query.filter(OperatorRole.manage_token == qParam.manage_token)
    # Company permissions
    if qParam.update_company is not None:
        query = query.filter(OperatorRole.update_company == qParam.update_company)
    # Operator permissions
    if qParam.create_operator is not None:
        query = query.filter(OperatorRole.create_operator == qParam.create_operator)
    if qParam.update_operator is not None:
        query = query.filter(OperatorRole.update_operator == qParam.update_operator)
    if qParam.delete_operator is not None:
        query = query.filter(OperatorRole.delete_operator == qParam.delete_operator)
    # Route permissions
    if qParam.create_route is not None:
        query = query.filter(OperatorRole.create_route == qParam.create_route)
    if qParam.update_route is not None:
        query = query.filter(OperatorRole.update_route == qParam.update_route)
    if qParam.delete_route is not None:
        query = query.filter(OperatorRole.delete_route == qParam.delete_route)
    # Bus permissions
    if qParam.create_bus is not None:
        query = query.filter(OperatorRole.create_bus == qParam.create_bus)
    if qParam.update_bus is not None:
        query = query.filter(OperatorRole.update_bus == qParam.update_bus)
    if qParam.delete_bus is not None:
        query = query.filter(OperatorRole.delete_bus == qParam.delete_bus)
    # Schedule permissions
    if qParam.create_schedule is not None:
        query = query.filter(OperatorRole.create_schedule == qParam.create_schedule)
    if qParam.update_schedule is not None:
        query = query.filter(OperatorRole.update_schedule == qParam.update_schedule)
    if qParam.delete_schedule is not None:
        query = query.filter(OperatorRole.delete_schedule == qParam.delete_schedule)
    # Service permissions
    if qParam.create_service is not None:
        query = query.filter(OperatorRole.create_service == qParam.create_service)
    if qParam.update_service is not None:
        query = query.filter(OperatorRole.update_service == qParam.update_service)
    if qParam.delete_service is not None:
        query = query.filter(OperatorRole.delete_service == qParam.delete_service)
    # Fare permissions
    if qParam.create_fare is not None:
        query = query.filter(OperatorRole.create_fare == qParam.create_fare)
    if qParam.update_fare is not None:
        query = query.filter(OperatorRole.update_fare == qParam.update_fare)
    if qParam.delete_fare is not None:
        query = query.filter(OperatorRole.delete_fare == qParam.delete_fare)
    # Duty permissions
    if qParam.create_duty is not None:
        query = query.filter(OperatorRole.create_duty == qParam.create_duty)
    if qParam.update_duty is not None:
        query = query.filter(OperatorRole.update_duty == qParam.update_duty)
    if qParam.delete_duty is not None:
        query = query.filter(OperatorRole.delete_duty == qParam.delete_duty)
    # Executive role permissions
    if qParam.create_role is not None:
        query = query.filter(OperatorRole.create_role == qParam.create_role)
    if qParam.update_role is not None:
        query = query.filter(OperatorRole.update_role == qParam.update_role)
    if qParam.delete_role is not None:
        query = query.filter(OperatorRole.delete_role == qParam.delete_role)
    # updated_on based
    if qParam.updated_on_ge is not None:
        query = query.filter(OperatorRole.updated_on >= qParam.updated_on_ge)
    if qParam.updated_on_le is not None:
        query = query.filter(OperatorRole.updated_on <= qParam.updated_on_le)
    # created_on based
    if qParam.created_on_ge is not None:
        query = query.filter(OperatorRole.created_on >= qParam.created_on_ge)
    if qParam.created_on_le is not None:
        query = query.filter(OperatorRole.created_on <= qParam.created_on_le)

    # Ordering
    orderingAttribute = getattr(OperatorRole, OrderBy(qParam.order_by).name)
    if qParam.order_in == OrderIn.ASC:
        query = query.order_by(orderingAttribute.asc())
    else:
        query = query.order_by(orderingAttribute.desc())

    # Pagination
    query = query.offset(qParam.offset).limit(qParam.limit)
    return query.all()


## API endpoints [Executive]
@route_executive.post(
    "/company/role",
    tags=["Operator Role"],
    response_model=OperatorRoleSchema,
    status_code=status.HTTP_201_CREATED,
    responses=makeExceptionResponses(
        [exceptions.InvalidToken, exceptions.NoPermission]
    ),
    description="""
    Create a new operator role.     
    Only authorized users with `create_op_role` permission can create a new role.      
    Role name must be unique across the company.        
    Log the role creation activity with the associated token.
    """,
)
async def create_role(
    fParam: CreateFormForEX = Depends(),
    bearer=Depends(bearer_executive),
    request_info=Depends(getters.requestInfo),
):
    try:
        session = sessionMaker()
        token = validators.executiveToken(bearer.credentials, session)
        role = getters.executiveRole(token, session)
        validators.executivePermission(role, ExecutiveRole.create_op_role)

        role = OperatorRole(
            name=fParam.name,
            company_id=fParam.company_id,
            manage_ex_token=fParam.manage_token,
            update_company=fParam.update_company,
            create_operator=fParam.create_operator,
            update_operator=fParam.update_operator,
            delete_operator=fParam.delete_operator,
            create_route=fParam.create_route,
            update_route=fParam.update_route,
            delete_route=fParam.delete_route,
            create_bus=fParam.create_bus,
            update_bus=fParam.update_bus,
            delete_bus=fParam.delete_bus,
            create_schedule=fParam.create_schedule,
            update_schedule=fParam.update_schedule,
            delete_schedule=fParam.delete_schedule,
            create_service=fParam.create_service,
            update_service=fParam.update_service,
            delete_service=fParam.delete_service,
            create_fare=fParam.create_fare,
            update_fare=fParam.update_fare,
            delete_fare=fParam.delete_fare,
            create_duty=fParam.create_duty,
            update_duty=fParam.update_duty,
            delete_duty=fParam.delete_duty,
            create_role=fParam.create_role,
            update_role=fParam.update_role,
            delete_role=fParam.delete_role,
        )
        session.add(role)
        session.commit()
        logEvent(token, request_info, jsonable_encoder(role))
        return role
    except Exception as e:
        exceptions.handle(e)
    finally:
        session.close()


@route_executive.patch(
    "/company/role",
    tags=["Operator Role"],
    response_model=OperatorRoleSchema,
    responses=makeExceptionResponses(
        [
            exceptions.InvalidToken,
            exceptions.NoPermission,
            exceptions.InvalidIdentifier,
        ]
    ),
    description="""
    Updates an existing operator role.       
    Only executives with `update_op_role` permission can perform this operation.    
    Support partial updates such as modifying the role name.       
    Changes are saved only if the role data has been modified.        
    Logs the role updating activity with the associated token.
    """,
)
async def update_role(
    fParam: UpdateForm = Depends(),
    bearer=Depends(bearer_executive),
    request_info=Depends(getters.requestInfo),
):
    try:
        session = sessionMaker()
        token = validators.executiveToken(bearer.credentials, session)
        role = getters.executiveRole(token, session)
        validators.executivePermission(role, ExecutiveRole.update_op_role)

        role = session.query(OperatorRole).filter(OperatorRole.id == fParam.id).first()
        if role is None:
            raise exceptions.InvalidIdentifier()

        updateRole(role, fParam)
        haveUpdates = session.is_modified(role)
        if haveUpdates:
            session.commit()
            session.refresh(role)

        roleData = jsonable_encoder(role)
        if haveUpdates:
            logEvent(token, request_info, roleData)
        return roleData
    except Exception as e:
        exceptions.handle(e)
    finally:
        session.close()


@route_executive.delete(
    "/company/role",
    tags=["Operator Role"],
    status_code=status.HTTP_204_NO_CONTENT,
    responses=makeExceptionResponses(
        [exceptions.InvalidToken, exceptions.NoPermission]
    ),
    description="""
    Deletes an existing operator role.       
    Only executives with `delete_op_role` permission can perform this operation.    
    Validates the role ID before deletion.       
    If the role exists, it is permanently removed from the system.       
    Logs the deletion activity using the executive's token and request metadata.
    """,
)
async def delete_role(
    fParam: DeleteForm = Depends(),
    bearer=Depends(bearer_executive),
    request_info=Depends(getters.requestInfo),
):
    try:
        session = sessionMaker()
        token = validators.executiveToken(bearer.credentials, session)
        role = getters.executiveRole(token, session)
        validators.executivePermission(role, ExecutiveRole.delete_op_role)

        role = session.query(OperatorRole).filter(OperatorRole.id == fParam.id).first()
        if role is not None:
            session.delete(role)
            session.commit()
            logEvent(token, request_info, jsonable_encoder(role))
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    except Exception as e:
        exceptions.handle(e)
    finally:
        session.close()


@route_executive.get(
    "/company/role",
    tags=["Operator Role"],
    response_model=List[OperatorRoleSchema],
    responses=makeExceptionResponses([exceptions.InvalidToken]),
    description="""
    Fetches a list of all operator role across companies.       
    Supports filtering by ID, name, permissions and metadata.   
    Supports filtering, sorting, and pagination.     
    Requires a valid executive token.
    """,
)
async def fetch_role(
    qParam: QueryParamsForEX = Depends(), bearer=Depends(bearer_executive)
):
    try:
        session = sessionMaker()
        validators.executiveToken(bearer.credentials, session)

        return searchRole(session, qParam)
    except Exception as e:
        exceptions.handle(e)
    finally:
        session.close()


## API endpoints [Operator]
@route_operator.post(
    "/company/role",
    tags=["Role"],
    response_model=OperatorRoleSchema,
    status_code=status.HTTP_201_CREATED,
    responses=makeExceptionResponses(
        [
            exceptions.InvalidToken,
            exceptions.NoPermission,
        ]
    ),
    description="""
    Creates a new operator role, associated with the current operator company.     
    Only operator with `create_role` permission can create role.        
    Logs the operator role creation activity with the associated token.             
    Duplicate names are not allowed.
    """,
)
async def create_role(
    fParam: CreateFormForOP = Depends(),
    bearer=Depends(bearer_operator),
    request_info=Depends(getters.requestInfo),
):
    try:
        session = sessionMaker()
        token = validators.operatorToken(bearer.credentials, session)
        role = getters.operatorRole(token, session)
        validators.operatorPermission(role, OperatorRole.create_role)

        role = OperatorRole(
            name=fParam.name,
            company_id=token.company_id,
            manage_ex_token=fParam.manage_token,
            update_company=fParam.update_company,
            create_operator=fParam.create_operator,
            update_operator=fParam.update_operator,
            delete_operator=fParam.delete_operator,
            create_route=fParam.create_route,
            update_route=fParam.update_route,
            delete_route=fParam.delete_route,
            create_bus=fParam.create_bus,
            update_bus=fParam.update_bus,
            delete_bus=fParam.delete_bus,
            create_schedule=fParam.create_schedule,
            update_schedule=fParam.update_schedule,
            delete_schedule=fParam.delete_schedule,
            create_service=fParam.create_service,
            update_service=fParam.update_service,
            delete_service=fParam.delete_service,
            create_fare=fParam.create_fare,
            update_fare=fParam.update_fare,
            delete_fare=fParam.delete_fare,
            create_duty=fParam.create_duty,
            update_duty=fParam.update_duty,
            delete_duty=fParam.delete_duty,
            create_role=fParam.create_role,
            update_role=fParam.update_role,
            delete_role=fParam.delete_role,
        )
        session.add(role)
        session.commit()
        logEvent(token, request_info, jsonable_encoder(role))
        return role
    except Exception as e:
        exceptions.handle(e)
    finally:
        session.close()


@route_operator.patch(
    "/company/role",
    tags=["Role"],
    response_model=OperatorRoleSchema,
    responses=makeExceptionResponses(
        [
            exceptions.InvalidToken,
            exceptions.NoPermission,
            exceptions.InvalidIdentifier,
        ]
    ),
    description="""
    Updates an existing operator role associated with the current operator company.             
    Operator with `update_role` permission can update other operators role.     
    Support partial updates such as modifying the role name.    
    Changes are saved only if the role data has been modified.         
    Logs the operator role update activity with the associated token.
    """,
)
async def update_role(
    fParam: UpdateForm = Depends(),
    bearer=Depends(bearer_operator),
    request_info=Depends(getters.requestInfo),
):
    try:
        session = sessionMaker()
        token = validators.operatorToken(bearer.credentials, session)
        role = getters.operatorRole(token, session)
        validators.operatorPermission(role, OperatorRole.update_role)

        role = (
            session.query(OperatorRole)
            .filter(OperatorRole.id == fParam.id)
            .filter(OperatorRole.company_id == token.company_id)
            .first()
        )
        if role is None:
            raise exceptions.InvalidIdentifier()

        updateRole(role, fParam)
        haveUpdates = session.is_modified(role)
        if haveUpdates:
            session.commit()
            session.refresh(role)

        roleData = jsonable_encoder(role)
        if haveUpdates:
            logEvent(token, request_info, roleData)
        return roleData
    except Exception as e:
        exceptions.handle(e)
    finally:
        session.close()


@route_operator.delete(
    "/company/role",
    tags=["Role"],
    status_code=status.HTTP_204_NO_CONTENT,
    responses=makeExceptionResponses(
        [
            exceptions.InvalidToken,
            exceptions.NoPermission,
        ]
    ),
    description="""
    Deletes an existing operator role.       
    Only users with the `delete_role` permission can delete operator accounts.       
    Validates the role ID before deletion.       
    If the role exists, it is permanently removed from the system.       
    Logs the deletion activity using the operator's token and request metadata. 
    """,
)
async def delete_role(
    fParam: DeleteForm = Depends(),
    bearer=Depends(bearer_operator),
    request_info=Depends(getters.requestInfo),
):
    try:
        session = sessionMaker()
        token = validators.operatorToken(bearer.credentials, session)
        role = getters.operatorRole(token, session)
        validators.operatorPermission(role, OperatorRole.delete_role)

        role = (
            session.query(OperatorRole)
            .filter(OperatorRole.id == fParam.id)
            .filter(OperatorRole.company_id == token.company_id)
            .first()
        )
        if role is not None:
            session.delete(role)
            session.commit()
            logEvent(token, request_info, jsonable_encoder(role))
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    except Exception as e:
        exceptions.handle(e)
    finally:
        session.close()


@route_operator.get(
    "/company/role",
    tags=["Role"],
    response_model=List[OperatorRoleSchema],
    responses=makeExceptionResponses([exceptions.InvalidToken]),
    description="""
    Fetches a list of all operator role across companies.       
    Supports filtering by ID, name, permissions and metadata.   
    Supports filtering, sorting, and pagination.     
    Requires a valid operator token.
    """,
)
async def fetch_role(
    qParam: QueryParamsForOP = Depends(), bearer=Depends(bearer_operator)
):
    try:
        session = sessionMaker()
        token = validators.operatorToken(bearer.credentials, session)

        qParam = QueryParamsForEX(**qParam.model_dump(), company_id=token.company_id)
        return searchRole(session, qParam)
    except Exception as e:
        exceptions.handle(e)
    finally:
        session.close()
