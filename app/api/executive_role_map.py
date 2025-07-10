from datetime import datetime
from enum import IntEnum
from typing import List, Optional
from fastapi import APIRouter, Depends, Query, Response, status, Form
from sqlalchemy.orm.session import Session
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
    pass


class CreateForm(BaseModel):
    pass


class UpdateForm(BaseModel):
    pass


class DeleteForm(BaseModel):
    pass


## Query Parameters
class OrderIn(IntEnum):
    pass


class OrderBy(IntEnum):
    pass


class QueryParams(BaseModel):
    pass


## API endpoints [Executive]
@route_executive.post(
    "/entebus/account/role",
    tags=["Executive Role"],
    response_model=ExecutiveRoleMapSchema,
    status_code=status.HTTP_201_CREATED,
    responses=makeExceptionResponses(
        [exceptions.InvalidToken, exceptions.NoPermission]
    ),
    description="""
    Assign a role to an executive account.    
    Only authorized users with `create_executive_role_map` permission can create a new role map.    
    Log the role map creation activity with the associated token.
    """,
)
async def create_executive_role_map(
    fParam: CreateForm = Depends(),
    bearer=Depends(bearer_executive),
    request_info=Depends(getters.requestInfo),
):
    pass


@route_executive.patch(
    "/entebus/account/role",
    tags=["Executive Role"],
    response_model=ExecutiveRoleMapSchema,
    responses=makeExceptionResponses(
        [exceptions.InvalidToken, exceptions.NoPermission, exceptions.InvalidIdentifier]
    ),
    description="""
    Update an existing role map.    
    Only authorized users with `update_executive_role_map` permission can update a role map.    
    Log the role map update activity with the associated token.
    """,
)
async def update_executive_role_map(
    fParam: UpdateForm = Depends(),
    bearer=Depends(bearer_executive),
    request_info=Depends(getters.requestInfo),
):
    pass


@route_executive.delete(
    "/entebus/account/role",
    tags=["Executive Role"],
    status_code=status.HTTP_204_NO_CONTENT,
    responses=makeExceptionResponses(
        [exceptions.InvalidToken, exceptions.NoPermission]
    ),
    description="""
    Unassign a role from an executive account.    
    Only authorized users with `delete_executive_role_map` permission can delete a role map.    
    Log the role map deletion activity with the associated token.
    """,
)
async def delete_executive_role_map(
    fParam: DeleteForm = Depends(),
    bearer=Depends(bearer_executive),
    request_info=Depends(getters.requestInfo),
):
    pass


@route_executive.get(
    "/entebus/account/role",
    tags=["Executive Role"],
    response_model=List[ExecutiveRoleMapSchema],
    responses=makeExceptionResponses([exceptions.InvalidToken]),
    description="""
    Retrieve a role map by ID.    
    Only authorized users with `retrieve_executive_role_map` permission can retrieve a role map.    
    Log the role map retrieval activity with the associated token.
    """,
)
async def retrieve_executive_role_map(
    fParam: DeleteForm = Depends(),
    bearer=Depends(bearer_executive),
    request_info=Depends(getters.requestInfo),
):
    pass
