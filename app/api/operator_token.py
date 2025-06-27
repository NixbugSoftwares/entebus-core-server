from datetime import datetime, timedelta, timezone
from enum import IntEnum
from secrets import token_hex
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

from app.api.bearer import bearer_executive, bearer_operator
from app.src.constants import (
    MAX_OPERATOR_TOKENS,
    MAX_TOKEN_VALIDITY,
)
from app.src.db import (
    ExecutiveRole,
    Operator,
    OperatorToken,
    sessionMaker,
)
from app.src import argon2, exceptions, validators, getters
from app.src.enums import AccountStatus, PlatformType
from app.src.loggers import logEvent
from app.src.functions import enumStr, makeExceptionResponses

route_operator = APIRouter()
route_executive = APIRouter()


## Output Schema
class MaskedOperatorTokenSchema(BaseModel):
    id: int
    operator_id: int
    company_id: int
    expires_in: int
    platform_type: int
    client_details: Optional[str]
    created_on: datetime
    updated_on: Optional[datetime]


class OperatorTokenSchema(MaskedOperatorTokenSchema):
    access_token: str
    token_type: Optional[str] = "bearer"


## Input Forms
class CreateForm(BaseModel):
    company_id: int = Field(Form())
    username: str = Field(Form(max_length=32))
    password: str = Field(Form(max_length=32))
    platform_type: PlatformType = Field(
        Form(description=enumStr(PlatformType), default=PlatformType.OTHER)
    )
    client_details: str | None = Field(Form(max_length=1024, default=None))


class DeleteFormForEX(BaseModel):
    id: int = Field(Form())


class DeleteForm(BaseModel):
    id: int | None = Field(Form(default=None))


class UpdateForm(BaseModel):
    id: int | None = Field(Form(default=None))


## Query Parameters
class OrderIn(IntEnum):
    ASC = 1
    DESC = 2


class OrderBy(IntEnum):
    id = 1
    updated_on = 2
    created_on = 3


class QueryParamsForOP(BaseModel):
    operator_id: int | None = Field(Query(default=None))
    platform_type: PlatformType | None = Field(
        Query(default=None, description=enumStr(PlatformType))
    )
    client_details: str | None = Field(Query(default=None))
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
def searchOperatorToken(
    session: Session, qParam: QueryParamsForEX | QueryParamsForOP
) -> List[OperatorToken]:
    query = session.query(OperatorToken)

    # Filters
    if qParam.operator_id is not None:
        query = query.filter(OperatorToken.operator_id == qParam.operator_id)
    if qParam.company_id is not None:
        query = query.filter(OperatorToken.company_id == qParam.company_id)
    if qParam.platform_type is not None:
        query = query.filter(OperatorToken.platform_type == qParam.platform_type)
    if qParam.client_details is not None:
        query = query.filter(
            OperatorToken.client_details.ilike(f"%{qParam.client_details}%")
        )
    # id based
    if qParam.id is not None:
        query = query.filter(OperatorToken.id == qParam.id)
    if qParam.id_ge is not None:
        query = query.filter(OperatorToken.id >= qParam.id_ge)
    if qParam.id_le is not None:
        query = query.filter(OperatorToken.id <= qParam.id_le)
    if qParam.id_list is not None:
        query = query.filter(OperatorToken.id.in_(qParam.id_list))
    # updated_on based
    if qParam.updated_on_ge is not None:
        query = query.filter(OperatorToken.updated_on >= qParam.updated_on_ge)
    if qParam.updated_on_le is not None:
        query = query.filter(OperatorToken.updated_on <= qParam.updated_on_le)
    # created_on based
    if qParam.created_on_ge is not None:
        query = query.filter(OperatorToken.created_on >= qParam.created_on_ge)
    if qParam.created_on_le is not None:
        query = query.filter(OperatorToken.created_on <= qParam.created_on_le)

    # Ordering
    orderingAttribute = getattr(OperatorToken, OrderBy(qParam.order_by).name)
    if qParam.order_in == OrderIn.ASC:
        query = query.order_by(orderingAttribute.asc())
    else:
        query = query.order_by(orderingAttribute.desc())

    # Pagination
    query = query.offset(qParam.offset).limit(qParam.limit)
    return query.all()


## API endpoints [Executive]
@route_executive.get(
    "/company/account/token",
    tags=["Operator token"],
    response_model=List[MaskedOperatorTokenSchema],
    responses=makeExceptionResponses(
        [exceptions.InvalidToken, exceptions.NoPermission]
    ),
    description="""
    Fetches a list of operator tokens belonging to a company, filtered by optional query parameters.    
    Only executives with `manage_op_token` permission can access this endpoint.     
    Supports filtering by token ID, operator ID, platform type, client details, and creation timestamps.    
    Enables pagination using offset and limit.   
    Allows sorting using order_by and order_i`.
    """,
)
async def fetch_tokens(
    qParam: QueryParamsForEX = Depends(), bearer=Depends(bearer_executive)
):
    try:
        session = sessionMaker()
        token = validators.executiveToken(bearer.credentials, session)
        role = getters.executiveRole(token, session)
        validators.executivePermission(role, ExecutiveRole.manage_op_token)

        return searchOperatorToken(session, qParam)
    except Exception as e:
        exceptions.handle(e)
    finally:
        session.close()


@route_executive.delete(
    "/company/account/token",
    tags=["Operator token"],
    status_code=status.HTTP_204_NO_CONTENT,
    responses=makeExceptionResponses(
        [exceptions.InvalidToken, exceptions.NoPermission]
    ),
    description="""
    Revokes an access token associated with an operator account.       
    This endpoint deletes an access token based on the operator token ID.    
    The executive with `manage_op_token` permission can delete any operator's token.    
    If the token ID is invalid or already deleted, the operation is silently ignored.   
    Logs the token revocation event for audit tracking if the id is valid.      
    """,
)
async def delete_token(
    fParam: DeleteFormForEX = Depends(),
    bearer=Depends(bearer_executive),
    request_info=Depends(getters.requestInfo),
):
    try:
        session = sessionMaker()
        token = validators.executiveToken(bearer.credentials, session)
        role = getters.executiveRole(token, session)
        validators.executivePermission(role, ExecutiveRole.manage_op_token)

        tokenToDelete = (
            session.query(OperatorToken).filter(OperatorToken.id == fParam.id).first()
        )
        if tokenToDelete is not None:
            session.delete(tokenToDelete)
            session.commit()
            logEvent(
                token,
                request_info,
                jsonable_encoder(tokenToDelete, exclude={"access_token"}),
            )
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    except Exception as e:
        exceptions.handle(e)
    finally:
        session.close()


## API endpoints [Operator]
@route_operator.post(
    "/company/account/token",
    tags=["Token"],
    response_model=OperatorTokenSchema,
    status_code=status.HTTP_201_CREATED,
    responses=makeExceptionResponses(
        [exceptions.InactiveAccount, exceptions.InvalidCredentials]
    ),
    description="""
    Issues a new access token for an operator after validating credentials.     
    This endpoint performs authentication using company_id, username and password submitted as form data.   
    If the credentials are valid and the operator account is active, a new token is generated and returned.     
    Limits active tokens using MAX_OPERATOR_TOKENS (token rotation).    
    Sets expiration with expires_in=MAX_TOKEN_VALIDITY (in seconds).    
    Token will be generated for ACTIVE operators only.      
    Logs the authentication event for audit tracking.
    """,
)
async def create_token(
    fParam: CreateForm = Depends(),
    request_info=Depends(getters.requestInfo),
):
    try:
        session = sessionMaker()
        operator = (
            session.query(Operator)
            .filter(Operator.username == fParam.username)
            .filter(Operator.company_id == fParam.company_id)
            .first()
        )
        if operator is None:
            raise exceptions.InvalidCredentials()

        if not argon2.checkPassword(fParam.password, operator.password):
            raise exceptions.InvalidCredentials()
        if operator.status != AccountStatus.ACTIVE:
            raise exceptions.InactiveAccount()

        # Remove excess tokens from DB
        tokens = (
            session.query(OperatorToken)
            .filter(OperatorToken.operator_id == operator.id)
            .order_by(OperatorToken.created_on.desc())
            .all()
        )
        if len(tokens) >= MAX_OPERATOR_TOKENS:
            token = tokens[MAX_OPERATOR_TOKENS - 1]
            session.delete(token)
            session.flush()

        # Create a new token
        expires_at = datetime.now(timezone.utc) + timedelta(seconds=MAX_TOKEN_VALIDITY)
        token = OperatorToken(
            company_id=fParam.company_id,
            operator_id=operator.id,
            expires_in=MAX_TOKEN_VALIDITY,
            expires_at=expires_at,
            platform_type=fParam.platform_type,
            client_details=fParam.client_details,
        )
        session.add(token)
        session.commit()
        logEvent(token, request_info, jsonable_encoder(token, exclude={"access_token"}))
        return token
    except Exception as e:
        exceptions.handle(e)
    finally:
        session.close()


@route_operator.patch(
    "/company/account/token",
    tags=["Token"],
    response_model=OperatorTokenSchema,
    responses=makeExceptionResponses(
        [exceptions.InvalidToken, exceptions.NoPermission, exceptions.InvalidIdentifier]
    ),
    description="""
    Refreshes an existing operator access token.    
    If no id is provided, refreshes only the current token (used in this request).      
    If an id is provided: Must match the current token's access_token (prevents unauthorized refreshes, even by the same operator).     
    Extends expires_at by MAX_TOKEN_VALIDITY seconds.   
    Rotates the access_token value (invalidates the old token immediately).   
    Logs the refresh event for auditability.
    """,
)
async def refresh_token(
    fParam: UpdateForm = Depends(),
    bearer=Depends(bearer_operator),
    request_info=Depends(getters.requestInfo),
):
    try:
        session = sessionMaker()
        token = validators.operatorToken(bearer.credentials, session)
        if fParam.id is None:
            tokenToUpdate = token
        else:
            tokenToUpdate = (
                session.query(OperatorToken)
                .filter(OperatorToken.id == fParam.id)
                .first()
            )
            if tokenToUpdate is None:
                raise exceptions.InvalidIdentifier()
            if tokenToUpdate.access_token != token.access_token:
                raise exceptions.NoPermission()

        tokenToUpdate.expires_in += MAX_TOKEN_VALIDITY
        tokenToUpdate.expires_at += timedelta(seconds=MAX_TOKEN_VALIDITY)
        tokenToUpdate.access_token = token_hex(32)
        session.commit()
        session.refresh(tokenToUpdate)
        logEvent(
            token,
            request_info,
            jsonable_encoder(tokenToUpdate, exclude={"access_token"}),
        )
        return tokenToUpdate
    except Exception as e:
        exceptions.handle(e)
    finally:
        session.close()


@route_operator.delete(
    "/company/account/token",
    tags=["Token"],
    status_code=status.HTTP_204_NO_CONTENT,
    responses=makeExceptionResponses(
        [exceptions.InvalidToken, exceptions.NoPermission]
    ),
    description="""
    Revokes an active access token associated with an operator account.     
    This endpoint deletes an access token based on the token ID (optional).     
    If no ID is provided, it deletes the token used in the request (self-revocation).       
    If an ID is provided, the caller must either, own the token being deleted, or have a role with `manage_token` permission.   
    If the token ID is invalid or already deleted, the operation is silently ignored.   
    Logs the token revocation event for audit tracking.
    """,
)
async def delete_token(
    fParam: DeleteForm = Depends(),
    bearer=Depends(bearer_operator),
    request_info=Depends(getters.requestInfo),
):
    try:
        session = sessionMaker()
        token = validators.operatorToken(bearer.credentials, session)
        role = getters.operatorRole(token, session)

        if fParam.id is None:
            tokenToDelete = token
        else:
            tokenToDelete = (
                session.query(OperatorToken)
                .filter(OperatorToken.id == fParam.id)
                .first()
            )
            if tokenToDelete is not None:
                isSelfDelete = token.operator_id == tokenToDelete.operator_id
                hasDeletePermission = bool(role and role.manage_token)
                if not isSelfDelete and not hasDeletePermission:
                    raise exceptions.NoPermission()
            else:
                return Response(status_code=status.HTTP_204_NO_CONTENT)

        session.delete(tokenToDelete)
        session.commit()
        logEvent(
            token,
            request_info,
            jsonable_encoder(tokenToDelete, exclude={"access_token"}),
        )
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    except Exception as e:
        exceptions.handle(e)
    finally:
        session.close()


@route_operator.get(
    "/company/account/token",
    tags=["Token"],
    response_model=List[MaskedOperatorTokenSchema],
    responses=makeExceptionResponses([exceptions.InvalidToken]),
    description="""
    Fetches a list of operator tokens filtered by optional query parameters.    
    Operators without `manage_token` permission can only retrieve their own tokens.  
    Supports filtering by ID range, platform type, client details, and creation timestamps.     
    Supports pagination with offset and limit.      
    Supports sorting using order_by and order_in.
    """,
)
async def fetch_tokens(
    qParam: QueryParamsForOP = Depends(), bearer=Depends(bearer_operator)
):
    try:
        session = sessionMaker()
        token = validators.operatorToken(bearer.credentials, session)

        qParam = QueryParamsForEX(**qParam.model_dump(), company_id=token.company_id)
        return searchOperatorToken(session, qParam)
    except Exception as e:
        exceptions.handle(e)
    finally:
        session.close()
