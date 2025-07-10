from datetime import datetime
from enum import IntEnum
from typing import List, Optional
from fastapi import APIRouter, Depends, Query, Response, status, Form
from fastapi.encoders import jsonable_encoder
from pydantic import BaseModel, Field

from app.api.bearer import bearer_executive
from app.src.db import ExecutiveRole, sessionMaker
from app.src import exceptions, validators, getters
from app.src.loggers import logEvent
from app.src.functions import enumStr, makeExceptionResponses

route_executive = APIRouter()


## Output Schema
class ExecutiveRoleSchema(BaseModel):
    id: int
    name: str
    manage_ex_token: bool
    manage_op_token: bool
    manage_ve_token: bool
    create_executive: bool
    update_executive: bool
    delete_executive: bool
    create_landmark: bool
    update_landmark: bool
    delete_landmark: bool
    create_company: bool
    update_company: bool
    delete_company: bool
    create_operator: bool
    update_operator: bool
    delete_operator: bool
    create_business: bool
    update_business: bool
    delete_business: bool
    create_route: bool
    update_route: bool
    delete_route: bool
    create_bus: bool
    update_bus: bool
    delete_bus: bool
    create_vendor: bool
    update_vendor: bool
    delete_vendor: bool
    create_schedule: bool
    update_schedule: bool
    delete_schedule: bool
    create_service: bool
    update_service: bool
    delete_service: bool
    create_fare: bool
    update_fare: bool
    delete_fare: bool
    create_ex_role: bool
    update_ex_role: bool
    delete_ex_role: bool
    updated_on: Optional[datetime]
    created_on: datetime


class CreateForm(BaseModel):
    name: str = Field(Form(max_length=32))
    manage_ex_token: bool = Field(Form(default=False))
    manage_op_token: bool = Field(Form(default=False))
    manage_ve_token: bool = Field(Form(default=False))
    create_executive: bool = Field(Form(default=False))
    update_executive: bool = Field(Form(default=False))
    delete_executive: bool = Field(Form(default=False))
    create_landmark: bool = Field(Form(default=False))
    update_landmark: bool = Field(Form(default=False))
    delete_landmark: bool = Field(Form(default=False))
    create_company: bool = Field(Form(default=False))
    update_company: bool = Field(Form(default=False))
    delete_company: bool = Field(Form(default=False))
    create_operator: bool = Field(Form(default=False))
    update_operator: bool = Field(Form(default=False))
    delete_operator: bool = Field(Form(default=False))
    create_business: bool = Field(Form(default=False))
    update_business: bool = Field(Form(default=False))
    delete_business: bool = Field(Form(default=False))
    create_route: bool = Field(Form(default=False))
    update_route: bool = Field(Form(default=False))
    delete_route: bool = Field(Form(default=False))
    create_bus: bool = Field(Form(default=False))
    update_bus: bool = Field(Form(default=False))
    delete_bus: bool = Field(Form(default=False))
    create_vendor: bool = Field(Form(default=False))
    update_vendor: bool = Field(Form(default=False))
    delete_vendor: bool = Field(Form(default=False))
    create_schedule: bool = Field(Form(default=False))
    update_schedule: bool = Field(Form(default=False))
    delete_schedule: bool = Field(Form(default=False))
    create_service: bool = Field(Form(default=False))
    update_service: bool = Field(Form(default=False))
    delete_service: bool = Field(Form(default=False))
    create_fare: bool = Field(Form(default=False))
    update_fare: bool = Field(Form(default=False))
    delete_fare: bool = Field(Form(default=False))
    create_ex_role: bool = Field(Form(default=False))
    update_ex_role: bool = Field(Form(default=False))
    delete_ex_role: bool = Field(Form(default=False))


class UpdateForm(BaseModel):
    id: int = Field(Form())
    name: str | None = Field(Form(max_length=32, default=None))
    manage_ex_token: bool | None = Field(Form(default=None))
    manage_op_token: bool | None = Field(Form(default=None))
    manage_ve_token: bool | None = Field(Form(default=None))
    create_executive: bool | None = Field(Form(default=None))
    update_executive: bool | None = Field(Form(default=None))
    delete_executive: bool | None = Field(Form(default=None))
    create_landmark: bool | None = Field(Form(default=None))
    update_landmark: bool | None = Field(Form(default=None))
    delete_landmark: bool | None = Field(Form(default=None))
    create_company: bool | None = Field(Form(default=None))
    update_company: bool | None = Field(Form(default=None))
    delete_company: bool | None = Field(Form(default=None))
    create_operator: bool | None = Field(Form(default=None))
    update_operator: bool | None = Field(Form(default=None))
    delete_operator: bool | None = Field(Form(default=None))
    create_business: bool | None = Field(Form(default=None))
    update_business: bool | None = Field(Form(default=None))
    delete_business: bool | None = Field(Form(default=None))
    create_route: bool | None = Field(Form(default=None))
    update_route: bool | None = Field(Form(default=None))
    delete_route: bool | None = Field(Form(default=None))
    create_bus: bool | None = Field(Form(default=None))
    update_bus: bool | None = Field(Form(default=None))
    delete_bus: bool | None = Field(Form(default=None))
    create_vendor: bool | None = Field(Form(default=None))
    update_vendor: bool | None = Field(Form(default=None))
    delete_vendor: bool | None = Field(Form(default=None))
    create_schedule: bool | None = Field(Form(default=None))
    update_schedule: bool | None = Field(Form(default=None))
    delete_schedule: bool | None = Field(Form(default=None))
    create_service: bool | None = Field(Form(default=None))
    update_service: bool | None = Field(Form(default=None))
    delete_service: bool | None = Field(Form(default=None))
    create_fare: bool | None = Field(Form(default=None))
    update_fare: bool | None = Field(Form(default=None))
    delete_fare: bool | None = Field(Form(default=None))
    create_ex_role: bool | None = Field(Form(default=None))
    update_ex_role: bool | None = Field(Form(default=None))
    delete_ex_role: bool | None = Field(Form(default=None))


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


class QueryParams(BaseModel):
    name: str | None = Field(Query(default=None))
    # id based
    id: int | None = Field(Query(default=None))
    id_ge: int | None = Field(Query(default=None))
    id_le: int | None = Field(Query(default=None))
    id_list: List[int] | None = Field(Query(default=None))
    # Token management permissions based
    manage_ex_token: bool | None = Field(Query(default=None))
    manage_op_token: bool | None = Field(Query(default=None))
    manage_ve_token: bool | None = Field(Query(default=None))
    # Executive management permissions based
    create_executive: bool | None = Field(Query(default=None))
    update_executive: bool | None = Field(Query(default=None))
    delete_executive: bool | None = Field(Query(default=None))
    # Landmark management permissions based
    create_landmark: bool | None = Field(Query(default=None))
    update_landmark: bool | None = Field(Query(default=None))
    delete_landmark: bool | None = Field(Query(default=None))
    # Company management permissions based
    create_company: bool | None = Field(Query(default=None))
    update_company: bool | None = Field(Query(default=None))
    delete_company: bool | None = Field(Query(default=None))
    # Operator management permissions based
    create_operator: bool | None = Field(Query(default=None))
    update_operator: bool | None = Field(Query(default=None))
    delete_operator: bool | None = Field(Query(default=None))
    # Business management permissions based
    create_business: bool | None = Field(Query(default=None))
    update_business: bool | None = Field(Query(default=None))
    delete_business: bool | None = Field(Query(default=None))
    # Route management permissions based
    create_route: bool | None = Field(Query(default=None))
    update_route: bool | None = Field(Query(default=None))
    delete_route: bool | None = Field(Query(default=None))
    # Bus management permissions based
    create_bus: bool | None = Field(Query(default=None))
    update_bus: bool | None = Field(Query(default=None))
    delete_bus: bool | None = Field(Query(default=None))
    # Vendor management permissions based
    create_vendor: bool | None = Field(Query(default=None))
    update_vendor: bool | None = Field(Query(default=None))
    delete_vendor: bool | None = Field(Query(default=None))
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
    # Executive role management permissions based
    create_ex_role: bool | None = Field(Query(default=None))
    update_ex_role: bool | None = Field(Query(default=None))
    delete_ex_role: bool | None = Field(Query(default=None))
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


## API endpoints [Executive]
@route_executive.post(
    "/entebus/role",
    tags=["Executive Role"],
    response_model=ExecutiveRoleSchema,
    status_code=status.HTTP_201_CREATED,
    responses=makeExceptionResponses(
        [exceptions.InvalidToken, exceptions.NoPermission]
    ),
    description="""
    Create a new executive role.     
    Only authorized users with `create_ex_role` permission can create a new role.      
    Duplicate names are not allowed.        
    Log the role creation activity with the associated token.
    """,
)
async def create_role(
    fParam: CreateForm = Depends(),
    bearer=Depends(bearer_executive),
    request_info=Depends(getters.requestInfo),
):
    try:
        session = sessionMaker()
        token = validators.executiveToken(bearer.credentials, session)
        role = getters.executiveRole(token, session)
        validators.executivePermission(role, ExecutiveRole.create_ex_role)

        role = ExecutiveRole(
            name=fParam.name,
            manage_ex_token=fParam.manage_ex_token,
            manage_op_token=fParam.manage_op_token,
            manage_ve_token=fParam.manage_ve_token,
            create_executive=fParam.create_executive,
            update_executive=fParam.update_executive,
            delete_executive=fParam.delete_executive,
            create_landmark=fParam.create_landmark,
            update_landmark=fParam.update_landmark,
            delete_landmark=fParam.delete_landmark,
            create_company=fParam.create_company,
            update_company=fParam.update_company,
            delete_company=fParam.delete_company,
            create_operator=fParam.create_operator,
            update_operator=fParam.update_operator,
            delete_operator=fParam.delete_operator,
            create_business=fParam.create_business,
            update_business=fParam.update_business,
            delete_business=fParam.delete_business,
            create_route=fParam.create_route,
            update_route=fParam.update_route,
            delete_route=fParam.delete_route,
            create_bus=fParam.create_bus,
            update_bus=fParam.update_bus,
            delete_bus=fParam.delete_bus,
            create_vendor=fParam.create_vendor,
            update_vendor=fParam.update_vendor,
            delete_vendor=fParam.delete_vendor,
            create_schedule=fParam.create_schedule,
            update_schedule=fParam.update_schedule,
            delete_schedule=fParam.delete_schedule,
            create_service=fParam.create_service,
            update_service=fParam.update_service,
            delete_service=fParam.delete_service,
            create_fare=fParam.create_fare,
            update_fare=fParam.update_fare,
            delete_fare=fParam.delete_fare,
            create_ex_role=fParam.create_ex_role,
            update_ex_role=fParam.update_ex_role,
            delete_ex_role=fParam.delete_ex_role,
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
    tags=["Executive Role"],
    response_model=ExecutiveRoleSchema,
    responses=makeExceptionResponses(
        [
            exceptions.InvalidToken,
            exceptions.NoPermission,
            exceptions.InvalidIdentifier,
        ]
    ),
    description="""
    Updates an existing role belonging.       
    Only executives with `update_ex_role` permission can perform this operation.            
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
        validators.executivePermission(role, ExecutiveRole.update_ex_role)

        role = (
            session.query(ExecutiveRole).filter(ExecutiveRole.id == fParam.id).first()
        )
        if role is None:
            raise exceptions.InvalidIdentifier()

        if fParam.name is not None:
            role.name = fParam.name
        if (
            fParam.manage_ex_token is not None
            and fParam.manage_ex_token != role.manage_ex_token
        ):
            role.manage_ex_token = fParam.manage_ex_token
        if (
            fParam.manage_op_token is not None
            and fParam.manage_op_token != role.manage_op_token
        ):
            role.manage_op_token = fParam.manage_op_token
        if (
            fParam.manage_ve_token is not None
            and fParam.manage_ve_token != role.manage_ve_token
        ):
            role.manage_ve_token = fParam.manage_ve_token
        if (
            fParam.create_executive is not None
            and fParam.create_executive != role.create_executive
        ):
            role.create_executive = fParam.create_executive
        if (
            fParam.update_executive is not None
            and fParam.update_executive != role.update_executive
        ):
            role.update_executive = fParam.update_executive
        if (
            fParam.delete_executive is not None
            and fParam.delete_executive != role.delete_executive
        ):
            role.delete_executive = fParam.delete_executive
        if (
            fParam.create_landmark is not None
            and fParam.create_landmark != role.create_landmark
        ):
            role.create_landmark = fParam.create_landmark
        if (
            fParam.update_landmark is not None
            and fParam.update_landmark != role.update_landmark
        ):
            role.update_landmark = fParam.update_landmark
        if (
            fParam.delete_landmark is not None
            and fParam.delete_landmark != role.delete_landmark
        ):
            role.delete_landmark = fParam.delete_landmark
        if (
            fParam.create_company is not None
            and fParam.create_company != role.create_company
        ):
            role.create_company = fParam.create_company
        if (
            fParam.update_company is not None
            and fParam.update_company != role.update_company
        ):
            role.update_company = fParam.update_company
        if (
            fParam.delete_company is not None
            and fParam.delete_company != role.delete_company
        ):
            role.delete_company = fParam.delete_company
        if (
            fParam.create_operator is not None
            and fParam.create_operator != role.create_operator
        ):
            role.create_operator = fParam.create_operator
        if (
            fParam.update_operator is not None
            and fParam.update_operator != role.update_operator
        ):
            role.update_operator = fParam.update_operator
        if (
            fParam.delete_operator is not None
            and fParam.delete_operator != role.delete_operator
        ):
            role.delete_operator = fParam.delete_operator
        if (
            fParam.create_business is not None
            and fParam.create_business != role.create_business
        ):
            role.create_business = fParam.create_business
        if (
            fParam.update_business is not None
            and fParam.update_business != role.update_business
        ):
            role.update_business = fParam.update_business
        if (
            fParam.delete_business is not None
            and fParam.delete_business != role.delete_business
        ):
            role.delete_business = fParam.delete_business
        if fParam.create_route is not None and fParam.create_route != role.create_route:
            role.create_route = fParam.create_route
        if fParam.update_route is not None and fParam.update_route != role.update_route:
            role.update_route = fParam.update_route
        if fParam.delete_route is not None and fParam.delete_route != role.delete_route:
            role.delete_route = fParam.delete_route
        if fParam.create_bus is not None and fParam.create_bus != role.create_bus:
            role.create_bus = fParam.create_bus
        if fParam.update_bus is not None and fParam.update_bus != role.update_bus:
            role.update_bus = fParam.update_bus
        if fParam.delete_bus is not None and fParam.delete_bus != role.delete_bus:
            role.delete_bus = fParam.delete_bus
        if (
            fParam.create_vendor is not None
            and fParam.create_vendor != role.create_vendor
        ):
            role.create_vendor = fParam.create_vendor
        if (
            fParam.update_vendor is not None
            and fParam.update_vendor != role.update_vendor
        ):
            role.update_vendor = fParam.update_vendor
        if (
            fParam.delete_vendor is not None
            and fParam.delete_vendor != role.delete_vendor
        ):
            role.delete_vendor = fParam.delete_vendor
        if (
            fParam.create_schedule is not None
            and fParam.create_schedule != role.create_schedule
        ):
            role.create_schedule = fParam.create_schedule
        if (
            fParam.update_schedule is not None
            and fParam.update_schedule != role.update_schedule
        ):
            role.update_schedule = fParam.update_schedule
        if (
            fParam.delete_schedule is not None
            and fParam.create_service != role.create_service
        ):
            role.delete_schedule = fParam.delete_schedule
        if (
            fParam.create_service is not None
            and fParam.create_service != role.create_service
        ):
            role.create_service = fParam.create_service
        if (
            fParam.update_service is not None
            and fParam.update_service != role.update_service
        ):
            role.update_service = fParam.update_service
        if (
            fParam.delete_service is not None
            and fParam.delete_service != role.delete_service
        ):
            role.delete_service = fParam.delete_service
        if fParam.create_fare is not None and fParam.create_fare != role.create_fare:
            role.create_fare = fParam.create_fare
        if fParam.update_fare is not None and fParam.update_fare != role.update_fare:
            role.update_fare = fParam.update_fare
        if fParam.delete_fare is not None and fParam.delete_fare != role.delete_fare:
            role.delete_fare = fParam.delete_fare
        if (
            fParam.create_ex_role is not None
            and fParam.create_ex_role != role.create_ex_role
        ):
            role.create_ex_role = fParam.create_ex_role
        if (
            fParam.update_ex_role is not None
            and fParam.update_ex_role != role.update_ex_role
        ):
            role.update_ex_role = fParam.update_ex_role
        if (
            fParam.delete_ex_role is not None
            and fParam.delete_ex_role != role.delete_ex_role
        ):
            role.delete_ex_role = fParam.delete_ex_role

        haveUpdates = session.is_modified(role)
        if haveUpdates:
            session.commit()
            session.refresh(role)
            logEvent(token, request_info, jsonable_encoder(role))
        return role
    except Exception as e:
        exceptions.handle(e)
    finally:
        session.close()


@route_executive.delete(
    "/company/role",
    tags=["Executive Role"],
    status_code=status.HTTP_204_NO_CONTENT,
    responses=makeExceptionResponses(
        [exceptions.InvalidToken, exceptions.NoPermission]
    ),
    description="""
    Deletes an existing role.       
    Only executives with `delete_ex_role` permission can perform this operation.    
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
        validators.executivePermission(role, ExecutiveRole.delete_ex_role)

        role = (
            session.query(ExecutiveRole).filter(ExecutiveRole.id == fParam.id).first()
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


@route_executive.get(
    "/entebus/role",
    tags=["Executive Role"],
    response_model=List[ExecutiveRoleSchema],
    responses=makeExceptionResponses([exceptions.InvalidToken]),
    description="""
    Fetches a list of all executive role.       
    Supports filtering by ID, name, permissions and metadata.   
    Supports filtering, sorting, and pagination.     
    Requires a valid executive token.
    """,
)
async def fetch_role(qParam: QueryParams = Depends(), bearer=Depends(bearer_executive)):
    try:
        session = sessionMaker()
        validators.executiveToken(bearer.credentials, session)

        query = session.query(ExecutiveRole)

        # Name filter
        if qParam.name is not None:
            query = query.filter(ExecutiveRole.name.ilike(f"%{qParam.name}%"))
        # ID based filters
        if qParam.id is not None:
            query = query.filter(ExecutiveRole.id == qParam.id)
        if qParam.id_ge is not None:
            query = query.filter(ExecutiveRole.id >= qParam.id_ge)
        if qParam.id_le is not None:
            query = query.filter(ExecutiveRole.id <= qParam.id_le)
        if qParam.id_list is not None:
            query = query.filter(ExecutiveRole.id.in_(qParam.id_list))
        # Token management permissions
        if qParam.manage_ex_token is not None:
            query = query.filter(
                ExecutiveRole.manage_ex_token == qParam.manage_ex_token
            )
        if qParam.manage_op_token is not None:
            query = query.filter(
                ExecutiveRole.manage_op_token == qParam.manage_op_token
            )
        if qParam.manage_ve_token is not None:
            query = query.filter(
                ExecutiveRole.manage_ve_token == qParam.manage_ve_token
            )
        # Executive management permissions
        if qParam.create_executive is not None:
            query = query.filter(
                ExecutiveRole.create_executive == qParam.create_executive
            )
        if qParam.update_executive is not None:
            query = query.filter(
                ExecutiveRole.update_executive == qParam.update_executive
            )
        if qParam.delete_executive is not None:
            query = query.filter(
                ExecutiveRole.delete_executive == qParam.delete_executive
            )
        # Landmark permissions
        if qParam.create_landmark is not None:
            query = query.filter(
                ExecutiveRole.create_landmark == qParam.create_landmark
            )
        if qParam.update_landmark is not None:
            query = query.filter(
                ExecutiveRole.update_landmark == qParam.update_landmark
            )
        if qParam.delete_landmark is not None:
            query = query.filter(
                ExecutiveRole.delete_landmark == qParam.delete_landmark
            )
        # Company permissions
        if qParam.create_company is not None:
            query = query.filter(ExecutiveRole.create_company == qParam.create_company)
        if qParam.update_company is not None:
            query = query.filter(ExecutiveRole.update_company == qParam.update_company)
        if qParam.delete_company is not None:
            query = query.filter(ExecutiveRole.delete_company == qParam.delete_company)
        # Operator permissions
        if qParam.create_operator is not None:
            query = query.filter(
                ExecutiveRole.create_operator == qParam.create_operator
            )
        if qParam.update_operator is not None:
            query = query.filter(
                ExecutiveRole.update_operator == qParam.update_operator
            )
        if qParam.delete_operator is not None:
            query = query.filter(
                ExecutiveRole.delete_operator == qParam.delete_operator
            )
        # Business permissions
        if qParam.create_business is not None:
            query = query.filter(
                ExecutiveRole.create_business == qParam.create_business
            )
        if qParam.update_business is not None:
            query = query.filter(
                ExecutiveRole.update_business == qParam.update_business
            )
        if qParam.delete_business is not None:
            query = query.filter(
                ExecutiveRole.delete_business == qParam.delete_business
            )
        # Route permissions
        if qParam.create_route is not None:
            query = query.filter(ExecutiveRole.create_route == qParam.create_route)
        if qParam.update_route is not None:
            query = query.filter(ExecutiveRole.update_route == qParam.update_route)
        if qParam.delete_route is not None:
            query = query.filter(ExecutiveRole.delete_route == qParam.delete_route)
        # Bus permissions
        if qParam.create_bus is not None:
            query = query.filter(ExecutiveRole.create_bus == qParam.create_bus)
        if qParam.update_bus is not None:
            query = query.filter(ExecutiveRole.update_bus == qParam.update_bus)
        if qParam.delete_bus is not None:
            query = query.filter(ExecutiveRole.delete_bus == qParam.delete_bus)
        # Vendor permissions
        if qParam.create_vendor is not None:
            query = query.filter(ExecutiveRole.create_vendor == qParam.create_vendor)
        if qParam.update_vendor is not None:
            query = query.filter(ExecutiveRole.update_vendor == qParam.update_vendor)
        if qParam.delete_vendor is not None:
            query = query.filter(ExecutiveRole.delete_vendor == qParam.delete_vendor)
        # Schedule permissions
        if qParam.create_schedule is not None:
            query = query.filter(
                ExecutiveRole.create_schedule == qParam.create_schedule
            )
        if qParam.update_schedule is not None:
            query = query.filter(
                ExecutiveRole.update_schedule == qParam.update_schedule
            )
        if qParam.delete_schedule is not None:
            query = query.filter(
                ExecutiveRole.delete_schedule == qParam.delete_schedule
            )
        # Service permissions
        if qParam.create_service is not None:
            query = query.filter(ExecutiveRole.create_service == qParam.create_service)
        if qParam.update_service is not None:
            query = query.filter(ExecutiveRole.update_service == qParam.update_service)
        if qParam.delete_service is not None:
            query = query.filter(ExecutiveRole.delete_service == qParam.delete_service)
        # Fare permissions
        if qParam.create_fare is not None:
            query = query.filter(ExecutiveRole.create_fare == qParam.create_fare)
        if qParam.update_fare is not None:
            query = query.filter(ExecutiveRole.update_fare == qParam.update_fare)
        if qParam.delete_fare is not None:
            query = query.filter(ExecutiveRole.delete_fare == qParam.delete_fare)
        # Executive role permissions
        if qParam.create_ex_role is not None:
            query = query.filter(ExecutiveRole.create_ex_role == qParam.create_ex_role)
        if qParam.update_ex_role is not None:
            query = query.filter(ExecutiveRole.update_ex_role == qParam.update_ex_role)
        if qParam.delete_ex_role is not None:
            query = query.filter(ExecutiveRole.delete_ex_role == qParam.delete_ex_role)
        # Date range filters
        if qParam.updated_on_ge is not None:
            query = query.filter(ExecutiveRole.updated_on >= qParam.updated_on_ge)
        if qParam.updated_on_le is not None:
            query = query.filter(ExecutiveRole.updated_on <= qParam.updated_on_le)
        if qParam.created_on_ge is not None:
            query = query.filter(ExecutiveRole.created_on >= qParam.created_on_ge)
        if qParam.created_on_le is not None:
            query = query.filter(ExecutiveRole.created_on <= qParam.created_on_le)

        # Ordering
        ordering_attr = getattr(ExecutiveRole, OrderBy(qParam.order_by).name)
        if qParam.order_in == OrderIn.ASC:
            query = query.order_by(ordering_attr.asc())
        else:
            query = query.order_by(ordering_attr.desc())

        # Pagination
        query = query.offset(qParam.offset).limit(qParam.limit)
        return query.all()

    except Exception as e:
        exceptions.handle(e)
    finally:
        session.close()
