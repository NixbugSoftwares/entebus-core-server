from datetime import datetime
from enum import IntEnum
from typing import List, Optional
from fastapi import APIRouter, Depends, Query, Response, status, Form
from fastapi.encoders import jsonable_encoder
from pydantic import BaseModel, Field
from sqlalchemy.orm.session import Session

from app.api.bearer import bearer_executive, bearer_operator
from app.src.db import (
    OperatorRole,
    ExecutiveRole,
    OperatorRoleMap,
    Operator,
    sessionMaker,
)
from app.src import exceptions, validators, getters
from app.src.loggers import logEvent
from app.src.functions import enumStr, makeExceptionResponses

route_executive = APIRouter()
route_operator = APIRouter()


## Output Schema
class OperatorRoleMapSchema(BaseModel):
    id: int
    company_id: int
    role_id: int
    operator_id: int
    updated_on: Optional[datetime]
    created_on: datetime


class CreateForm(BaseModel):
    role_id: int = Field(Form())
    operator_id: int = Field(Form())


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


class QueryParamsForOP(BaseModel):
    # Filters
    role_id: int | None = Field(Query(default=None))
    operator_id: int | None = Field(Query(default=None))
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


class QueryParamsForEX(QueryParamsForOP):
    company_id: int | None = Field(Query(default=None))


## Functions
def createRoleMap(role: OperatorRole, operator: Operator):
    if role.company_id != operator.company_id:
        raise exceptions.InvalidAssociation(
            OperatorRoleMap.role_id, OperatorRoleMap.company_id
        )
    return OperatorRoleMap(
        role_id=role.id, operator_id=operator.id, company_id=operator.company_id
    )


def updateRoleMap(session: Session, roleMap: OperatorRoleMap, fParam: UpdateForm):
    if fParam.role_id is not None and roleMap.role_id != fParam.role_id:
        role = (
            session.query(OperatorRole)
            .filter(OperatorRole.id == fParam.role_id)
            .first()
        )
        if role is None:
            raise exceptions.UnknownValue(OperatorRoleMap.role_id)
        if role.company_id != roleMap.company_id:
            raise exceptions.InvalidAssociation(
                OperatorRoleMap.role_id, OperatorRoleMap.company_id
            )
        roleMap.role_id = fParam.role_id


def searchRoleMap(
    session: Session, qParam: QueryParamsForOP | QueryParamsForEX
) -> List[OperatorRoleMap]:
    query = session.query(OperatorRoleMap)

    if qParam.role_id is not None:
        query = query.filter(OperatorRoleMap.role_id == qParam.role_id)
    if qParam.operator_id is not None:
        query = query.filter(OperatorRoleMap.operator_id == qParam.operator_id)
    if qParam.company_id is not None:
        query = query.filter(OperatorRoleMap.company_id == qParam.company_id)
    # id based
    if qParam.id is not None:
        query = query.filter(OperatorRoleMap.id == qParam.id)
    if qParam.id_ge is not None:
        query = query.filter(OperatorRoleMap.id >= qParam.id_ge)
    if qParam.id_le is not None:
        query = query.filter(OperatorRoleMap.id <= qParam.id_le)
    if qParam.id_list is not None:
        query = query.filter(OperatorRoleMap.id.in_(qParam.id_list))
    # updated_on based
    if qParam.updated_on_ge is not None:
        query = query.filter(OperatorRoleMap.updated_on >= qParam.updated_on_ge)
    if qParam.updated_on_le is not None:
        query = query.filter(OperatorRoleMap.updated_on <= qParam.updated_on_le)
    # created_on based
    if qParam.created_on_ge is not None:
        query = query.filter(OperatorRoleMap.created_on >= qParam.created_on_ge)
    if qParam.created_on_le is not None:
        query = query.filter(OperatorRoleMap.created_on <= qParam.created_on_le)

    # Ordering
    orderingAttribute = getattr(OperatorRoleMap, OrderBy(qParam.order_by).name)
    if qParam.order_in == OrderIn.ASC:
        query = query.order_by(orderingAttribute.asc())
    else:
        query = query.order_by(orderingAttribute.desc())

    # Pagination
    query = query.offset(qParam.offset).limit(qParam.limit)
    return query.all()


## API endpoints [Executive]
@route_executive.post(
    "/company/account/role",
    tags=["Operator Role Map"],
    response_model=OperatorRoleMapSchema,
    status_code=status.HTTP_201_CREATED,
    responses=makeExceptionResponses(
        [
            exceptions.InvalidToken,
            exceptions.NoPermission,
            exceptions.UnknownValue(OperatorRoleMap.operator_id),
            exceptions.InvalidAssociation(
                OperatorRoleMap.role_id, OperatorRoleMap.company_id
            ),
        ]
    ),
    description="""
    Assign a role to an operator account.    
    Only authorized users with `update_op_role` permission can create a new role map.    
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
        validators.executivePermission(role, ExecutiveRole.update_op_role)

        operator = (
            session.query(Operator).filter(Operator.id == fParam.operator_id).first()
        )
        if operator is None:
            raise exceptions.UnknownValue(OperatorRoleMap.operator_id)
        role = (
            session.query(OperatorRole)
            .filter(OperatorRole.id == fParam.role_id)
            .first()
        )
        if role is None:
            raise exceptions.UnknownValue(OperatorRoleMap.role_id)
        roleMap = createRoleMap(role, operator)

        session.add(roleMap)
        session.commit()
        session.refresh(roleMap)

        roleMapData = jsonable_encoder(roleMap)
        logEvent(token, request_info, roleMapData)
        return roleMapData
    except Exception as e:
        exceptions.handle(e)
    finally:
        session.close()


@route_executive.patch(
    "/company/account/role",
    tags=["Operator Role Map"],
    response_model=OperatorRoleMapSchema,
    responses=makeExceptionResponses(
        [
            exceptions.InvalidToken,
            exceptions.NoPermission,
            exceptions.InvalidIdentifier,
            exceptions.UnknownValue(OperatorRoleMap.role_id),
            exceptions.InvalidAssociation(
                OperatorRoleMap.role_id, OperatorRoleMap.company_id
            ),
        ]
    ),
    description="""
    Updates an existing role maps.       
    Only executives with `update_op_role` permission can perform this operation.    
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
        validators.executivePermission(role, ExecutiveRole.update_op_role)

        roleMap = (
            session.query(OperatorRoleMap)
            .filter(OperatorRoleMap.id == fParam.id)
            .first()
        )
        if roleMap is None:
            raise exceptions.InvalidIdentifier()

        updateRoleMap(session, roleMap, fParam)
        haveUpdates = session.is_modified(roleMap)
        if haveUpdates:
            session.commit()
            session.refresh(roleMap)

        roleMapData = jsonable_encoder(roleMap)
        if haveUpdates:
            logEvent(token, request_info, roleMapData)
        return roleMapData
    except Exception as e:
        exceptions.handle(e)
    finally:
        session.close()


@route_executive.delete(
    "/company/account/role",
    tags=["Operator Role Map"],
    status_code=status.HTTP_204_NO_CONTENT,
    responses=makeExceptionResponses(
        [exceptions.InvalidToken, exceptions.NoPermission]
    ),
    description="""
    Deletes an existing operator role maps.       
    Only executives with `update_op_role` permission can perform this operation.    
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
        validators.executivePermission(role, ExecutiveRole.update_op_role)

        roleMap = (
            session.query(OperatorRoleMap)
            .filter(OperatorRoleMap.id == fParam.id)
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
    "/company/account/role",
    tags=["Operator Role Map"],
    response_model=List[OperatorRoleMapSchema],
    responses=makeExceptionResponses([exceptions.InvalidToken]),
    description="""
    Fetches a list of all operator role maps across companies.       
    Supports filtering by ID and metadata.   
    Supports filtering, sorting, and pagination.     
    Requires a valid executive token.
    """,
)
async def fetch_role_map(
    qParam: QueryParamsForEX = Depends(), bearer=Depends(bearer_executive)
):
    try:
        session = sessionMaker()
        validators.executiveToken(bearer.credentials, session)

        return searchRoleMap(session, qParam)
    except Exception as e:
        exceptions.handle(e)
    finally:
        session.close()


## API endpoints [Operator]
@route_operator.post(
    "/company/account/role",
    tags=["Role Map"],
    response_model=OperatorRoleMapSchema,
    status_code=status.HTTP_201_CREATED,
    responses=makeExceptionResponses(
        [
            exceptions.InvalidToken,
            exceptions.NoPermission,
            exceptions.UnknownValue(OperatorRoleMap.operator_id),
            exceptions.InvalidAssociation(
                OperatorRoleMap.role_id, OperatorRoleMap.company_id
            ),
        ]
    ),
    description="""
    Assign a role to an operator account, associated with the current operator company.       
    Only authorized users with `update_role` permission can create a new role map.    
    Log the role map creation activity with the associated token.
    """,
)
async def create_role_map(
    fParam: CreateForm = Depends(),
    bearer=Depends(bearer_operator),
    request_info=Depends(getters.requestInfo),
):
    try:
        session = sessionMaker()
        token = validators.operatorToken(bearer.credentials, session)
        role = getters.operatorRole(token, session)
        validators.operatorPermission(role, OperatorRole.update_role)

        operator = (
            session.query(Operator)
            .filter(Operator.id == fParam.operator_id)
            .filter(Operator.company_id == token.company_id)
            .first()
        )
        if operator is None:
            raise exceptions.UnknownValue(OperatorRoleMap.operator_id)
        role = (
            session.query(OperatorRole)
            .filter(OperatorRole.id == fParam.role_id)
            .filter(OperatorRole.company_id == token.company_id)
            .first()
        )
        if role is None:
            raise exceptions.UnknownValue(OperatorRoleMap.role_id)
        roleMap = createRoleMap(role, operator)

        session.add(roleMap)
        session.commit()
        session.refresh(roleMap)

        roleMapData = jsonable_encoder(roleMap)
        logEvent(token, request_info, roleMapData)
        return roleMapData
    except Exception as e:
        exceptions.handle(e)
    finally:
        session.close()


@route_operator.patch(
    "/company/account/role",
    tags=["Role Map"],
    response_model=OperatorRoleMapSchema,
    responses=makeExceptionResponses(
        [
            exceptions.InvalidToken,
            exceptions.NoPermission,
            exceptions.InvalidIdentifier,
            exceptions.UnknownValue(OperatorRoleMap.role_id),
            exceptions.InvalidAssociation(
                OperatorRoleMap.role_id, OperatorRoleMap.company_id
            ),
        ]
    ),
    description="""
    Updates an existing role map, associated with the current operator company.            
    Operator with `update_role` permission can update other operators role.  
    Support partial updates such as modifying the role_id.       
    Logs the role map update activity with the associated token.
    """,
)
async def update_role_map(
    fParam: UpdateForm = Depends(),
    bearer=Depends(bearer_operator),
    request_info=Depends(getters.requestInfo),
):
    try:
        session = sessionMaker()
        token = validators.operatorToken(bearer.credentials, session)
        role = getters.operatorRole(token, session)
        validators.operatorPermission(role, OperatorRole.update_role)

        roleMap = (
            session.query(OperatorRoleMap)
            .filter(OperatorRoleMap.id == fParam.id)
            .filter(OperatorRoleMap.company_id == token.company_id)
            .first()
        )
        if roleMap is None:
            raise exceptions.InvalidIdentifier()

        updateRoleMap(session, roleMap, fParam)
        haveUpdates = session.is_modified(roleMap)
        if haveUpdates:
            session.commit()
            session.refresh(roleMap)

        roleMapData = jsonable_encoder(roleMap)
        if haveUpdates:
            logEvent(token, request_info, roleMapData)
        return roleMapData
    except Exception as e:
        exceptions.handle(e)
    finally:
        session.close()


@route_operator.delete(
    "/company/account/role",
    tags=["Role Map"],
    status_code=status.HTTP_204_NO_CONTENT,
    responses=makeExceptionResponses(
        [exceptions.InvalidToken,exceptions.NoPermission]
    ),
    description="""
    Deletes an existing operator role map.       
    Only users with the `update_role` permission can delete operator role maps.     
    Validates the role map ID before deletion.       
    If the role map exists, it is permanently removed from the system.       
    Logs the deletion activity using the operator's token and request metadata.        
    """,
)
async def delete_role_map(
    fParam: DeleteForm = Depends(),
    bearer=Depends(bearer_operator),
    request_info=Depends(getters.requestInfo),
):
    try:
        session = sessionMaker()
        token = validators.operatorToken(bearer.credentials, session)
        role = getters.operatorRole(token, session)
        validators.operatorPermission(role, OperatorRole.update_role)

        roleMap = (
            session.query(OperatorRoleMap)
            .filter(OperatorRoleMap.id == fParam.id)
            .filter(OperatorRoleMap.company_id == token.company_id)
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


@route_operator.get(
    "/company/account/role",
    tags=["Role Map"],
    response_model=List[OperatorRoleMapSchema],
    responses=makeExceptionResponses([exceptions.InvalidToken]),
    description="""
    Fetches a list of all operator role maps for the current operator company.       
    Supports filtering by ID and metadata.   
    Supports filtering, sorting, and pagination.     
    Requires a valid operator token.
    """,
)
async def fetch_role_map(
    qParam: QueryParamsForOP = Depends(), bearer=Depends(bearer_operator)
):
    try:
        session = sessionMaker()
        token = validators.operatorToken(bearer.credentials, session)

        qParam = QueryParamsForEX(**qParam.model_dump(), company_id=token.company_id)
        return searchRoleMap(session, qParam)
    except Exception as e:
        exceptions.handle(e)
    finally:
        session.close()
