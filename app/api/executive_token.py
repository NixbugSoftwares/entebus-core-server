from datetime import datetime, timedelta, timezone
from enum import IntEnum
from secrets import token_hex
from typing import List, Optional
from fastapi import APIRouter, Depends, Query, Response, status, Form
from fastapi.encoders import jsonable_encoder
from pydantic import BaseModel, Field

from app.api.bearer import bearer_executive
from app.src.constants import MAX_EXECUTIVE_TOKENS, MAX_TOKEN_VALIDITY
from app.src.db import Executive, ExecutiveToken, sessionMaker
from app.src import argon2, exceptions, validators, getters
from app.src.enums import AccountStatus, PlatformType
from app.src.loggers import logEvent
from app.src.functions import enumStr, fuseExceptionResponses
from app.src.urls import URL_EXECUTIVE_TOKEN

route_executive = APIRouter()


## Output Schema
class MaskedExecutiveTokenSchema(BaseModel):
    id: int
    executive_id: int
    expires_in: int
    platform_type: int
    client_details: Optional[str]
    updated_on: Optional[datetime]
    created_on: datetime


class ExecutiveTokenSchema(MaskedExecutiveTokenSchema):
    access_token: str
    token_type: Optional[str] = "bearer"


## Input Forms
class CreateForm(BaseModel):
    username: str = Field(Form(max_length=32))
    password: str = Field(Form(max_length=32))
    platform_type: PlatformType = Field(
        Form(description=enumStr(PlatformType), default=PlatformType.OTHER)
    )
    client_details: str | None = Field(Form(max_length=1024, default=None))


class UpdateForm(BaseModel):
    id: int | None = Field(Form(default=None))


class DeleteForm(BaseModel):
    id: int | None = Field(Form(default=None))


## Query Parameters
class OrderIn(IntEnum):
    ASC = 1
    DESC = 2


class OrderBy(IntEnum):
    id = 1
    updated_on = 2
    created_on = 3


class QueryParams(BaseModel):
    executive_id: int | None = Field(Query(default=None))
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


## API endpoints [Executive]
@route_executive.post(
    URL_EXECUTIVE_TOKEN,
    tags=["Token"],
    response_model=ExecutiveTokenSchema,
    status_code=status.HTTP_201_CREATED,
    responses=fuseExceptionResponses(
        [exceptions.InactiveAccount(), exceptions.InvalidCredentials()]
    ),
    description="""
    Issues a new access token for an executive after validating credentials.    
    If the credentials are valid and the executive account is active, a new token is generated and returned.    
    Limits active tokens using MAX_EXECUTIVE_TOKENS (token rotation).   
    Sets expiration with expires_in=MAX_TOKEN_VALIDITY (in seconds).    
    Logs the authentication event for audit tracking.
    """,
)
async def create_token(
    fParam: CreateForm = Depends(),
    request_info=Depends(getters.requestInfo),
):
    try:
        session = sessionMaker()
        executive = (
            session.query(Executive)
            .filter(Executive.username == fParam.username)
            .first()
        )
        if executive is None:
            raise exceptions.InvalidCredentials()

        if not argon2.checkPassword(fParam.password, executive.password):
            raise exceptions.InvalidCredentials()
        if executive.status != AccountStatus.ACTIVE:
            raise exceptions.InactiveAccount()

        # Remove excess tokens from DB
        tokens = (
            session.query(ExecutiveToken)
            .filter(ExecutiveToken.executive_id == executive.id)
            .order_by(ExecutiveToken.created_on.desc())
            .all()
        )
        if len(tokens) >= MAX_EXECUTIVE_TOKENS:
            token = tokens[MAX_EXECUTIVE_TOKENS - 1]
            session.delete(token)
            session.flush()

        # Create a new token
        expires_at = datetime.now(timezone.utc) + timedelta(seconds=MAX_TOKEN_VALIDITY)
        token = ExecutiveToken(
            executive_id=executive.id,
            expires_in=MAX_TOKEN_VALIDITY,
            expires_at=expires_at,
            platform_type=fParam.platform_type,
            client_details=fParam.client_details,
        )
        session.add(token)
        session.commit()
        session.refresh(token)

        tokenData = jsonable_encoder(token)
        tokenLogData = tokenData.copy()
        tokenLogData.pop("access_token")
        logEvent(token, request_info, tokenLogData)
        return tokenData
    except Exception as e:
        exceptions.handle(e)
    finally:
        session.close()


@route_executive.patch(
    URL_EXECUTIVE_TOKEN,
    tags=["Token"],
    response_model=ExecutiveTokenSchema,
    responses=fuseExceptionResponses(
        [
            exceptions.InvalidToken(),
            exceptions.NoPermission(),
            exceptions.InvalidIdentifier(),
        ]
    ),
    description="""
    Refreshes an existing executive access token.
    If no id is provided, refreshes only the current token (used in this request).  
    If an id is provided: Must match the current token's access_token (prevents unauthorized refreshes, even by the same executive).    
    Raises InvalidIdentifier if the token does not exist (avoids ID probing).   
    Extends expires_at by MAX_TOKEN_VALIDITY seconds.   
    Rotates the access_token value (invalidates the old token immediately). 
    Logs the refresh event for auditability.
    """,
)
async def refresh_token(
    fParam: UpdateForm = Depends(),
    bearer=Depends(bearer_executive),
    request_info=Depends(getters.requestInfo),
):
    try:
        session = sessionMaker()
        token = validators.executiveToken(bearer.credentials, session)

        if fParam.id is None:
            tokenToUpdate = token
        else:
            tokenToUpdate = (
                session.query(ExecutiveToken)
                .filter(ExecutiveToken.id == fParam.id)
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

        tokenData = jsonable_encoder(tokenToUpdate)
        tokenLogData = tokenData.copy()
        tokenLogData.pop("access_token")
        logEvent(token, request_info, tokenLogData)
        return tokenData
    except Exception as e:
        exceptions.handle(e)
    finally:
        session.close()


@route_executive.delete(
    URL_EXECUTIVE_TOKEN,
    tags=["Token"],
    status_code=status.HTTP_204_NO_CONTENT,
    responses=fuseExceptionResponses(
        [exceptions.InvalidToken(), exceptions.NoPermission()]
    ),
    description="""
    Revokes an active access token associated with an executive account.    
    This endpoint deletes an access token based on the token ID (optional). 
    If no ID is provided, it deletes the token used in the request (self-revocation).   
    If an ID is provided, the caller must either, own the token being deleted, or have a role with `manage_ex_token` permission. 
    If the token ID is invalid or already deleted, the operation is silently ignored.   
    Logs the token revocation event for audit tracking.
    """,
)
async def delete_token(
    fParam: DeleteForm = Depends(),
    bearer=Depends(bearer_executive),
    request_info=Depends(getters.requestInfo),
):
    try:
        session = sessionMaker()
        token = validators.executiveToken(bearer.credentials, session)
        role = getters.executiveRole(token, session)

        if fParam.id is None:
            tokenToDelete = token
        else:
            tokenToDelete = (
                session.query(ExecutiveToken)
                .filter(ExecutiveToken.id == fParam.id)
                .first()
            )
            if tokenToDelete is not None:
                isSelfDelete = token.executive_id == tokenToDelete.executive_id
                hasDeletePermission = bool(role and role.manage_ex_token)
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


@route_executive.get(
    URL_EXECUTIVE_TOKEN,
    tags=["Token"],
    response_model=List[MaskedExecutiveTokenSchema],
    responses=fuseExceptionResponses([exceptions.InvalidToken()]),
    description="""
    Retrieves access tokens associated with executive accounts.     
    If the authenticated user has the `manage_ex_token` permission, all masked tokens from the ExecutiveToken table are returned.     
    If the authenticated user don't have manage_ex_token permission, only their own masked tokens are returned.     
    Returns a list of masked token data, excluding access_token content.    
    Useful for reviewing active or historical token usage management.
    """,
)
async def fetch_tokens(
    qParam: QueryParams = Depends(), bearer=Depends(bearer_executive)
):
    try:
        session = sessionMaker()
        token = validators.executiveToken(bearer.credentials, session)
        role = getters.executiveRole(token, session)
        canManageToken = bool(role and role.manage_ex_token)

        query = session.query(ExecutiveToken)

        # Filters
        if qParam.executive_id is not None:
            query = query.filter(ExecutiveToken.executive_id == qParam.executive_id)
        if canManageToken is False:
            query = query.filter(ExecutiveToken.executive_id == token.executive_id)
        if qParam.platform_type is not None:
            query = query.filter(ExecutiveToken.platform_type == qParam.platform_type)
        if qParam.client_details is not None:
            query = query.filter(
                ExecutiveToken.client_details.ilike(f"%{qParam.client_details}%")
            )
        # id based
        if qParam.id is not None:
            query = query.filter(ExecutiveToken.id == qParam.id)
        if qParam.id_ge is not None:
            query = query.filter(ExecutiveToken.id >= qParam.id_ge)
        if qParam.id_le is not None:
            query = query.filter(ExecutiveToken.id <= qParam.id_le)
        if qParam.id_list is not None:
            query = query.filter(ExecutiveToken.id.in_(qParam.id_list))
        # updated_on based
        if qParam.updated_on_ge is not None:
            query = query.filter(ExecutiveToken.updated_on >= qParam.updated_on_ge)
        if qParam.updated_on_le is not None:
            query = query.filter(ExecutiveToken.updated_on <= qParam.updated_on_le)
        # created_on based
        if qParam.created_on_ge is not None:
            query = query.filter(ExecutiveToken.created_on >= qParam.created_on_ge)
        if qParam.created_on_le is not None:
            query = query.filter(ExecutiveToken.created_on <= qParam.created_on_le)

        # Ordering
        orderingAttribute = getattr(ExecutiveToken, OrderBy(qParam.order_by).name)
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
