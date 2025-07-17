from datetime import datetime
from enum import IntEnum
from typing import List, Optional
from fastapi import APIRouter, Depends, Query, Response, status, Form
from sqlalchemy.orm.session import Session
from fastapi.encoders import jsonable_encoder
from pydantic import BaseModel, Field, EmailStr
from pydantic_extra_types.phone_numbers import PhoneNumber

from app.api.bearer import bearer_executive, bearer_operator
from app.src.constants import REGEX_PASSWORD, REGEX_USERNAME
from app.src.db import (
    ExecutiveRole,
    Operator,
    OperatorRole,
    OperatorToken,
    sessionMaker,
)
from app.src import argon2, exceptions, validators, getters
from app.src.enums import AccountStatus, GenderType
from app.src.loggers import logEvent
from app.src.functions import enumStr, makeExceptionResponses
from app.src.functions import promoteToParent

route_operator = APIRouter()
route_executive = APIRouter()


## Output Schema
class OperatorSchema(BaseModel):
    id: int
    company_id: int
    username: str
    gender: int
    full_name: Optional[str]
    status: int
    phone_number: Optional[str]
    email_id: Optional[str]
    updated_on: Optional[datetime]
    created_on: datetime


## Input Forms
class CreateFormForOP(BaseModel):
    username: str = Field(Form(pattern=REGEX_USERNAME, min_length=4, max_length=32))
    password: str = Field(Form(pattern=REGEX_PASSWORD, min_length=8, max_length=32))
    gender: GenderType = Field(
        Form(description=enumStr(GenderType), default=GenderType.OTHER)
    )
    full_name: str | None = Field(Form(max_length=32, default=None))
    phone_number: PhoneNumber | None = Field(
        Form(max_length=32, default=None, description="Phone number in RFC3966 format")
    )
    email_id: EmailStr | None = Field(
        Form(max_length=256, default=None, description="Email in RFC 5322 format")
    )


class CreateFormForEX(CreateFormForOP):
    company_id: int = Field(Form())


class UpdateFormForOP(BaseModel):
    id: int | None = Field(Form(default=None))
    password: str | None = Field(
        Form(pattern=REGEX_PASSWORD, min_length=8, max_length=32, default=None)
    )
    gender: GenderType | None = Field(
        Form(description=enumStr(GenderType), default=None)
    )
    full_name: str | None = Field(Form(max_length=32, default=None))
    status: AccountStatus | None = Field(
        Form(description=enumStr(AccountStatus), default=None)
    )
    phone_number: PhoneNumber | None = Field(
        Form(max_length=32, default=None, description="Phone number in RFC3966 format")
    )
    email_id: EmailStr | None = Field(
        Form(max_length=256, default=None, description="Email in RFC 5322 format")
    )


class UpdateFormForEX(UpdateFormForOP):
    id: int = Field(Form())


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
    username: str | None = Field(Query(default=None))
    gender: GenderType | None = Field(
        Query(default=None, description=enumStr(GenderType))
    )
    full_name: str | None = Field(Query(default=None))
    status: AccountStatus | None = Field(
        Query(default=None, description=enumStr(AccountStatus))
    )
    phone_number: str | None = Field(Query(default=None))
    email_id: str | None = Field(Query(default=None))
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


## Function
def updateOperator(
    session: Session, operator: Operator, fParam: UpdateFormForOP | UpdateFormForEX
):
    if fParam.password is not None:
        operator.password = argon2.makePassword(fParam.password)
    if fParam.gender is not None and operator.gender != fParam.gender:
        operator.gender = fParam.gender
    if fParam.full_name is not None and operator.full_name != fParam.full_name:
        operator.full_name = fParam.full_name
    if fParam.phone_number is not None and operator.phone_number != fParam.phone_number:
        operator.phone_number = fParam.phone_number
    if fParam.email_id is not None and operator.email_id != fParam.email_id:
        operator.email_id = fParam.email_id
    if fParam.status is not None and operator.status != fParam.status:
        if fParam.status == AccountStatus.SUSPENDED:
            session.query(OperatorToken).filter(
                OperatorToken.operator_id == fParam.id
            ).delete()
        operator.status = fParam.status


def searchOperator(
    session: Session, qParam: QueryParamsForOP | QueryParamsForEX
) -> List[Operator]:
    query = session.query(Operator)

    # Filters
    if qParam.username is not None:
        query = query.filter(Operator.username.ilike(f"%{qParam.username}%"))
    if qParam.company_id is not None:
        query = query.filter(Operator.company_id == qParam.company_id)
    if qParam.gender is not None:
        query = query.filter(Operator.gender == qParam.gender)
    if qParam.full_name is not None:
        query = query.filter(Operator.full_name.ilike(f"%{qParam.full_name}%"))
    if qParam.phone_number is not None:
        query = query.filter(Operator.phone_number.ilike(f"%{qParam.phone_number}%"))
    if qParam.email_id is not None:
        query = query.filter(Operator.email_id.ilike(f"%{qParam.email_id}%"))
    if qParam.status is not None:
        query = query.filter(Operator.status == qParam.status)
    # id based
    if qParam.id is not None:
        query = query.filter(Operator.id == qParam.id)
    if qParam.id_ge is not None:
        query = query.filter(Operator.id >= qParam.id_ge)
    if qParam.id_le is not None:
        query = query.filter(Operator.id <= qParam.id_le)
    if qParam.id_list is not None:
        query = query.filter(Operator.id.in_(qParam.id_list))
    # updated_on based
    if qParam.updated_on_ge is not None:
        query = query.filter(Operator.updated_on >= qParam.updated_on_ge)
    if qParam.updated_on_le is not None:
        query = query.filter(Operator.updated_on <= qParam.updated_on_le)
    # created_on based
    if qParam.created_on_ge is not None:
        query = query.filter(Operator.created_on >= qParam.created_on_ge)
    if qParam.created_on_le is not None:
        query = query.filter(Operator.created_on <= qParam.created_on_le)

    # Ordering
    orderingAttribute = getattr(Operator, OrderBy(qParam.order_by).name)
    if qParam.order_in == OrderIn.ASC:
        query = query.order_by(orderingAttribute.asc())
    else:
        query = query.order_by(orderingAttribute.desc())

    # Pagination
    query = query.offset(qParam.offset).limit(qParam.limit)
    return query.all()


## API endpoints [Executive]
@route_executive.post(
    "/company/account",
    tags=["Operator Account"],
    response_model=OperatorSchema,
    status_code=status.HTTP_201_CREATED,
    responses=makeExceptionResponses(
        [exceptions.InvalidToken, exceptions.NoPermission]
    ),
    description="""
    Creates a new operator account with an active status.       
    Only executive with `create_operator` permission can create operator.       
    Logs the operator account creation activity with the associated token.     
    Follow patterns for smooth creation of username and password.       
    The password is hashed using Argon2 before storing.
    """,
)
async def create_operator(
    fParam: CreateFormForEX = Depends(),
    bearer=Depends(bearer_executive),
    request_info=Depends(getters.requestInfo),
):
    try:
        session = sessionMaker()
        token = validators.executiveToken(bearer.credentials, session)
        role = getters.executiveRole(token, session)
        validators.executivePermission(role, ExecutiveRole.create_operator)

        fParam.password = argon2.makePassword(fParam.password)
        operator = Operator(
            company_id=fParam.company_id,
            username=fParam.username,
            password=fParam.password,
            gender=fParam.gender,
            full_name=fParam.full_name,
            phone_number=fParam.phone_number,
            email_id=fParam.email_id,
        )
        session.add(operator)
        session.commit()
        session.refresh(operator)

        operatorData = jsonable_encoder(operator, exclude={"password"})
        logEvent(token, request_info, operatorData)
        return operatorData
    except Exception as e:
        exceptions.handle(e)
    finally:
        session.close()


@route_executive.patch(
    "/company/account",
    tags=["Operator Account"],
    response_model=OperatorSchema,
    responses=makeExceptionResponses(
        [exceptions.InvalidToken, exceptions.NoPermission, exceptions.InvalidIdentifier]
    ),
    description="""
    Updates an existing operator account.       
    Executive with `update_operator` permission can update operators.     
    Follow patterns for smooth creation of password.        
    The password is hashed using Argon2 before storing.         
    If the status is set to`SUSPENDED, all tokens associated with that operator are revoked.      
    Logs the operator account update activity with the associated token.
    """,
)
async def update_operator(
    fParam: UpdateFormForEX = Depends(),
    bearer=Depends(bearer_executive),
    request_info=Depends(getters.requestInfo),
):
    try:
        session = sessionMaker()
        token = validators.executiveToken(bearer.credentials, session)
        role = getters.executiveRole(token, session)
        validators.executivePermission(role, ExecutiveRole.update_operator)

        operator = session.query(Operator).filter(Operator.id == fParam.id).first()
        if operator is None:
            raise exceptions.InvalidIdentifier()

        updateOperator(session, operator, fParam)
        haveUpdates = session.is_modified(operator)
        if haveUpdates:
            session.commit()
            session.refresh(operator)

        operatorData = jsonable_encoder(operator, exclude={"password"})
        if haveUpdates:
            logEvent(token, request_info, operatorData)
        return operatorData
    except Exception as e:
        exceptions.handle(e)
    finally:
        session.close()


@route_executive.delete(
    "/company/account",
    tags=["Operator Account"],
    status_code=status.HTTP_204_NO_CONTENT,
    responses=makeExceptionResponses(
        [exceptions.InvalidToken, exceptions.NoPermission]
    ),
    description="""
    Delete an existing operator by ID.  
    Requires executive permissions with `delete_operator` role.  
    Deletes the operator and logs the deletion event.
    """,
)
async def delete_operator(
    fParam: DeleteForm = Depends(),
    bearer=Depends(bearer_executive),
    request_info=Depends(getters.requestInfo),
):
    try:
        session = sessionMaker()
        token = validators.executiveToken(bearer.credentials, session)
        role = getters.executiveRole(token, session)
        validators.executivePermission(role, OperatorRole.delete_operator)

        operator = session.query(Operator).filter(Operator.id == fParam.id).first()
        if operator is not None:
            session.delete(operator)
            session.commit()
            logEvent(
                token, request_info, jsonable_encoder(operator, exclude={"password"})
            )
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    except Exception as e:
        exceptions.handle(e)
    finally:
        session.close()


@route_executive.get(
    "/company/account",
    tags=["Operator Account"],
    response_model=List[OperatorSchema],
    responses=makeExceptionResponses([exceptions.InvalidToken]),
    description="""
    Fetch operator accounts with filtering, sorting, and pagination.    
    Filter by company_id, username, gender, designation, contact details, status, and creation/update timestamps.   
    Filter by ID ranges or lists.    
    Sort by ID, creation date, or update date in ascending or descending order.     
    Paginate using offset and limit.    
    Returns a list of operator accounts matching the criteria.      
    Requires a valid executive token.
    """,
)
async def fetch_operator(
    qParam: QueryParamsForEX = Depends(), bearer=Depends(bearer_executive)
):
    try:
        session = sessionMaker()
        validators.executiveToken(bearer.credentials, session)

        return searchOperator(session, qParam)
    except Exception as e:
        exceptions.handle(e)
    finally:
        session.close()


## API endpoints [Operator]
@route_operator.post(
    "/company/account",
    tags=["Account"],
    response_model=OperatorSchema,
    status_code=status.HTTP_201_CREATED,
    responses=makeExceptionResponses(
        [exceptions.InvalidToken, exceptions.NoPermission]
    ),
    description="""
    Creates a new operator account with an active status, associated with the current operator company.     
    Only operator with `create_operator` permission can create operator.        
    Logs the operator account creation activity with the associated token.      
    Follow patterns for smooth creation of username and password.       
    The password is hashed using Argon2 before storing.         
    Duplicate usernames are not allowed.
    """,
)
async def create_operator(
    fParam: CreateFormForOP = Depends(),
    bearer=Depends(bearer_operator),
    request_info=Depends(getters.requestInfo),
):
    try:
        session = sessionMaker()
        token = validators.operatorToken(bearer.credentials, session)
        role = getters.operatorRole(token, session)
        validators.operatorPermission(role, OperatorRole.create_operator)

        fParam.password = argon2.makePassword(fParam.password)
        operator = Operator(
            company_id=token.company_id,
            username=fParam.username,
            password=fParam.password,
            gender=fParam.gender,
            full_name=fParam.full_name,
            phone_number=fParam.phone_number,
            email_id=fParam.email_id,
        )
        session.add(operator)
        session.commit()

        session.refresh(operator)

        operatorData = jsonable_encoder(operator, exclude={"password"})
        logEvent(token, request_info, operatorData)
        return operatorData
    except Exception as e:
        exceptions.handle(e)
    finally:
        session.close()


@route_operator.patch(
    "/company/account",
    tags=["Account"],
    response_model=OperatorSchema,
    responses=makeExceptionResponses(
        [exceptions.InvalidToken, exceptions.NoPermission, exceptions.InvalidIdentifier]
    ),
    description="""
    Updates an existing operator account associated with the current operator company.      
    Operator can update their own account but cannot update their own status.       
    Operator with `update_operator` permission can update other operators.      
    Follow patterns for smooth creation of username and password.       
    Password changes are securely hashed.       
    If the status is set to SUSPENDED, all tokens associated with that operator are revoked.      
    Logs the operator account update activity with the associated token.
    """,
)
async def update_operator(
    fParam: UpdateFormForOP = Depends(),
    bearer=Depends(bearer_operator),
    request_info=Depends(getters.requestInfo),
):
    try:
        session = sessionMaker()
        token = validators.operatorToken(bearer.credentials, session)
        role = getters.operatorRole(token, session)

        if fParam.id is None:
            fParam.id = token.operator_id
        isSelfUpdate = fParam.id == token.operator_id
        hasUpdatePermission = bool(role and role.update_operator)
        if not isSelfUpdate and not hasUpdatePermission:
            raise exceptions.NoPermission()
        if fParam.status == AccountStatus.SUSPENDED and isSelfUpdate:
            raise exceptions.NoPermission()

        operator = (
            session.query(Operator)
            .filter(Operator.id == fParam.id)
            .filter(Operator.company_id == token.company_id)
            .first()
        )
        if operator is None:
            raise exceptions.InvalidIdentifier()

        updateOperator(session, operator, fParam)
        haveUpdates = session.is_modified(operator)
        if haveUpdates:
            session.commit()
            session.refresh(operator)

        operatorData = jsonable_encoder(operator, exclude={"password"})
        if haveUpdates:
            logEvent(token, request_info, operatorData)
        return operatorData
    except Exception as e:
        exceptions.handle(e)
    finally:
        session.close()


@route_operator.delete(
    "/company/account",
    tags=["Account"],
    status_code=status.HTTP_204_NO_CONTENT,
    responses=makeExceptionResponses(
        [exceptions.InvalidToken, exceptions.NoPermission]
    ),
    description="""
    Delete an operator account associated with the current operator company.        
    Only users with the `delete_operator` permission can delete operator accounts.        
    Self-deletion is not allowed for safety reasons.    
    If the specified operator exists, it will be deleted permanently.    
    The deleted account details are logged for audit purposes.
    """,
)
async def delete_operator(
    fParam: DeleteForm = Depends(),
    bearer=Depends(bearer_operator),
    request_info=Depends(getters.requestInfo),
):
    try:
        session = sessionMaker()
        token = validators.operatorToken(bearer.credentials, session)
        role = getters.operatorRole(token, session)
        validators.operatorPermission(role, OperatorRole.delete_operator)

        # Prevent self deletion
        if fParam.id == token.operator_id:
            raise exceptions.NoPermission()

        operator = (
            session.query(Operator)
            .filter(Operator.id == fParam.id)
            .filter(Operator.company_id == token.company_id)
            .first()
        )
        if operator is not None:
            session.delete(operator)
            session.commit()
            logEvent(
                token, request_info, jsonable_encoder(operator, exclude={"password"})
            )
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    except Exception as e:
        exceptions.handle(e)
    finally:
        session.close()


@route_operator.get(
    "/company/account",
    tags=["Account"],
    response_model=List[OperatorSchema],
    responses=makeExceptionResponses([exceptions.InvalidToken]),
    description="""
    Fetch the operator information associated with the current operator company.     
    Filter by username, gender, designation, contact details, status, and creation/update timestamps.      
    Filter by ID ranges or lists.       
    Sort by ID, creation date, or update date in ascending or descending order.     
    Paginate using offset and limit.        
    Returns a list of operator accounts matching the criteria.      
    Requires a valid operator token.
    """,
)
async def fetch_operator(
    qParam: QueryParamsForOP = Depends(), bearer=Depends(bearer_operator)
):
    try:
        session = sessionMaker()
        token = validators.operatorToken(bearer.credentials, session)

        qParam = promoteToParent(qParam, QueryParamsForEX, company_id=token.company_id)
        return searchOperator(session, qParam)
    except Exception as e:
        exceptions.handle(e)
    finally:
        session.close()
