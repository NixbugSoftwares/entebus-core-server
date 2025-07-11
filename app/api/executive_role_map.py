from datetime import datetime
from enum import IntEnum
from typing import List, Optional
from fastapi import APIRouter, Depends, Query, Response, status, Form
from fastapi.encoders import jsonable_encoder
from pydantic import BaseModel, Field

from app.api.bearer import bearer_executive
from app.src.db import ExecutiveRole, ExecutiveRoleMap, sessionMaker
from app.src import exceptions, validators, getters
from app.src.loggers import logEvent
from app.src.functions import enumStr, makeExceptionResponses

route_executive = APIRouter()


## Output Schema
class ExecutiveRoleMapSchema(BaseModel):
    id: int
    role_id: int
    executive_id: int
    updated_on: Optional[datetime]
    created_on: datetime


class CreateForm(BaseModel):
    role_id: int = Field(Form())
    executive_id: int = Field(Form())


class UpdateForm(BaseModel):
    id: int = Field(Form())
    role_id: int | None = Field(Form(default=None))


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
    # Filters
    role_id: int | None = Field(Query(default=None))
    executive_id: int | None = Field(Query(default=None))
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


## API endpoints [Executive]
@route_executive.post(
    "/account/role",
    tags=["Role Map"],
    response_model=ExecutiveRoleMapSchema,
    status_code=status.HTTP_201_CREATED,
    responses=makeExceptionResponses(
        [exceptions.InvalidToken, exceptions.NoPermission]
    ),
    description="""
    Assign a role to an executive account.    
    Only authorized users with `update_ex_role` permission can create a new role map.    
    Log the role map creation activity with the associated token.
    """,
)
async def create_role_map(
    fParam: CreateForm = Depends(),
    bearer=Depends(bearer_executive),
    request_info=Depends(getters.requestInfo),
):
    try:
        session = sessionMaker()
        token = validators.executiveToken(bearer.credentials, session)
        role = getters.executiveRole(token, session)
        validators.executivePermission(role, ExecutiveRole.update_ex_role)

        roleMap = ExecutiveRoleMap(
            role_id=fParam.role_id, executive_id=fParam.executive_id
        )
        session.add(roleMap)
        session.commit()
        logEvent(token, request_info, jsonable_encoder(roleMap))
        return roleMap
    except Exception as e:
        exceptions.handle(e)
    finally:
        session.close()


@route_executive.patch(
    "/account/role",
    tags=["Role Map"],
    response_model=ExecutiveRoleMapSchema,
    responses=makeExceptionResponses(
        [
            exceptions.InvalidToken,
            exceptions.NoPermission,
            exceptions.InvalidIdentifier,
        ]
    ),
    description="""
    Updates an existing role maps.       
    Only executives with `update_ex_role` permission can perform this operation.    
    Support partial updates such as modifying the role_id.        
    Logs the role map updating activity with the associated token.
    """,
)
async def update_role_map(
    fParam: UpdateForm = Depends(),
    bearer=Depends(bearer_executive),
    request_info=Depends(getters.requestInfo),
):
    try:
        session = sessionMaker()
        token = validators.executiveToken(bearer.credentials, session)
        role = getters.executiveRole(token, session)
        validators.executivePermission(role, ExecutiveRole.update_ex_role)

        roleMap = (
            session.query(ExecutiveRoleMap)
            .filter(ExecutiveRoleMap.id == fParam.id)
            .first()
        )
        if roleMap is None:
            raise exceptions.InvalidIdentifier()
        if fParam.role_id is not None and fParam.role_id != roleMap.role_id:
            roleMap.role_id = fParam.role_id

        haveUpdates = session.is_modified(roleMap)
        if haveUpdates:
            session.commit()
            session.refresh(roleMap)

        roleMapData = jsonable_encoder(role)
        if haveUpdates:
            logEvent(token, request_info, roleMapData)
        return roleMapData
    except Exception as e:
        exceptions.handle(e)
    finally:
        session.close()


@route_executive.delete(
    "/account/role",
    tags=["Role Map"],
    status_code=status.HTTP_204_NO_CONTENT,
    responses=makeExceptionResponses(
        [exceptions.InvalidToken, exceptions.NoPermission]
    ),
    description="""
    Deletes an existing role maps.       
    Only executives with `update_ex_role` permission can perform this operation.    
    Validates the role map ID before deletion.       
    If the mapping exists, it is permanently removed from the system.       
    Logs the deletion activity using the executive's token and request metadata.
    """,
)
async def delete_role_map(
    fParam: DeleteForm = Depends(),
    bearer=Depends(bearer_executive),
    request_info=Depends(getters.requestInfo),
):
    try:
        session = sessionMaker()
        token = validators.executiveToken(bearer.credentials, session)
        role = getters.executiveRole(token, session)
        validators.executivePermission(role, ExecutiveRole.update_ex_role)

        roleMap = (
            session.query(ExecutiveRoleMap)
            .filter(ExecutiveRoleMap.id == fParam.id)
            .first()
        )
        if roleMap is not None:
            session.delete(roleMap)
            session.commit()
            logEvent(token, request_info, jsonable_encoder(roleMap))
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    except Exception as e:
        exceptions.handle(e)
    finally:
        session.close()


@route_executive.get(
    "/account/role",
    tags=["Role Map"],
    response_model=List[ExecutiveRoleMapSchema],
    responses=makeExceptionResponses([exceptions.InvalidToken]),
    description="""
    Fetches a list of all executive role maps.       
    Supports filtering by ID and metadata.   
    Supports filtering, sorting, and pagination.     
    Requires a valid executive token.
    """,
)
async def fetch_role_map(
    qParam: QueryParams = Depends(), bearer=Depends(bearer_executive)
):
    try:
        session = sessionMaker()
        validators.executiveToken(bearer.credentials, session)

        query = session.query(ExecutiveRoleMap)

        # Filters
        if qParam.role_id is not None:
            query = query.filter(ExecutiveRoleMap.role_id == qParam.role_id)
        if qParam.executive_id is not None:
            query = query.filter(ExecutiveRoleMap.executive_id == qParam.executive_id)
        if qParam.id is not None:
            query = query.filter(ExecutiveRoleMap.id == qParam.id)
        if qParam.id_ge is not None:
            query = query.filter(ExecutiveRoleMap.id >= qParam.id_ge)
        if qParam.id_le is not None:
            query = query.filter(ExecutiveRoleMap.id <= qParam.id_le)
        if qParam.id_list is not None:
            query = query.filter(ExecutiveRoleMap.id.in_(qParam.id_list))
        # updated_on based
        if qParam.updated_on_ge is not None:
            query = query.filter(ExecutiveRoleMap.updated_on >= qParam.updated_on_ge)
        if qParam.updated_on_le is not None:
            query = query.filter(ExecutiveRoleMap.updated_on <= qParam.updated_on_le)
        # created_on based
        if qParam.created_on_ge is not None:
            query = query.filter(ExecutiveRoleMap.created_on >= qParam.created_on_ge)
        if qParam.created_on_le is not None:
            query = query.filter(ExecutiveRoleMap.created_on <= qParam.created_on_le)

        # Ordering
        orderingAttribute = getattr(ExecutiveRoleMap, OrderBy(qParam.order_by).name)
        if qParam.order_in == OrderIn.ASC:
            query = query.order_by(orderingAttribute.asc())
        else:
            query = query.order_by(orderingAttribute.desc())

        # Pagination
        query = query.offset(qParam.offset).limit(qParam.limit)
        return query.all()
    except Exception as e:
        exceptions.handle(e)
    finally:
        session.close()
