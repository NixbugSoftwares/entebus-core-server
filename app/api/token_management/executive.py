from typing import Annotated, List
from fastapi import APIRouter, Depends, Form, status, Query
from fastapi.encoders import jsonable_encoder
from datetime import datetime, timedelta, timezone
from enum import IntEnum

from app.api.bearer import bearer_executive
from app.src.constants import MAX_EXECUTIVE_TOKENS, MAX_TOKEN_VALIDITY
from app.src.enums import AccountStatus, PlatformType, OrderIn
from app.src import schemas
from app.src.db import sessionMaker, Executive, ExecutiveToken
from app.src import argon2, exceptions
from app.src.functions import (
    enumStr,
    getRequestInfo,
    logExecutiveEvent,
    makeExceptionResponses,
    getExecutiveToken,
    getExecutiveRole,
)


route_executive = APIRouter()


## Schemas
class OrderBy(IntEnum):
    id = 1
    created_on = 2


## API endpoints
@route_executive.post(
    "/entebus/account/token",
    tags=["Token"],
    response_model=schemas.ExecutiveToken,
    status_code=status.HTTP_201_CREATED,
    responses=makeExceptionResponses(
        [exceptions.InactiveAccount, exceptions.InvalidCredentials]
    ),
    description="""
    Issues a new access token for an executive after validating credentials.

    - This endpoint performs authentication using username and password submitted as form data. 
    - If the credentials are valid and the executive account is active, a new token is generated and returned.
    - Limits active tokens using MAX_EXECUTIVE_TOKENS (token rotation).
    - Sets expiration with expires_in=MAX_TOKEN_VALIDITY (in seconds).
    - Logs the authentication event for audit tracking.
    """,
)
async def create_token(
    username: Annotated[str, Form(max_length=32)],
    password: Annotated[str, Form(max_length=32)],
    platform_type: Annotated[
        PlatformType, Form(description=enumStr(PlatformType))
    ] = PlatformType.OTHER,
    client_details: Annotated[str | None, Form(max_length=1024)] = None,
    request_info=Depends(getRequestInfo),
):
    try:
        session = sessionMaker()
        executive = (
            session.query(Executive).filter(Executive.username == username).first()
        )
        if executive is None:
            raise exceptions.InvalidCredentials()

        if not argon2.checkPassword(password, executive.password):
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
            platform_type=platform_type,
            client_details=client_details,
        )
        session.add(token)
        session.commit()
        logExecutiveEvent(
            token, request_info, jsonable_encoder(token, exclude={"access_token"})
        )
        return token
    except Exception as e:
        exceptions.handle(e)
    finally:
        session.close()


@route_executive.patch("/entebus/account/token", tags=["Token"])
async def update_token(credential=Depends(bearer_executive)):
    pass


@route_executive.get(
    "/entebus/account/token",
    tags=["Token"],
    response_model=List[schemas.MaskedExecutiveToken],
    responses=makeExceptionResponses([exceptions.InvalidToken]),
    description="""  
    Retrieves access tokens associated with executive accounts.

    - This endpoint allows filtering tokens using below mentioned parameters.
    - If the authenticated user has the manage_ex_token permission, all masked tokens from the ExecutiveToken table are returned.
    - If the authenticated user don't have manage_ex_token permission, only their own masked tokens are returned.
    - Supports pagination with `offset` and `limit` query parameters.
    - Supports ordering by `id` or `created_on`, in ascending or descending order.
    - Returns a list of masked token data, excluding access token content.
    - Useful for reviewing active or historical token usage management.
    """,
)
async def fetch_tokens(
    id: Annotated[int, Query()] = None,
    id_ge: Annotated[int, Query()] = None,
    id_le: Annotated[int, Query()] = None,
    executive_id: Annotated[int, Query()] = None,
    platform_type: Annotated[
        PlatformType, Query(description=enumStr(PlatformType))
    ] = None,
    client_details: Annotated[str, Query()] = None,
    created_on: Annotated[datetime, Query()] = None,
    created_on_ge: Annotated[datetime, Query()] = None,
    created_on_le: Annotated[datetime, Query()] = None,
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(gt=0, le=100)] = 20,
    order_by: Annotated[OrderBy, Query(description=enumStr(OrderBy))] = OrderBy.id,
    order_in: Annotated[OrderIn, Query(description=enumStr(OrderIn))] = OrderIn.DESC,
    access_token=Depends(bearer_executive),
):
    try:
        session = sessionMaker()
        token = getExecutiveToken(access_token.credentials, session)
        if token is None:
            raise exceptions.InvalidToken()
        role = getExecutiveRole(token, session)

        havePermission = False
        if role is not None and role.manage_ex_token is True:
            havePermission = True

        query = session.query(ExecutiveToken)
        if executive_id is not None:
            query = query.filter(ExecutiveToken.executive_id == executive_id)
        if not havePermission:
            query = query.filter(ExecutiveToken.executive_id == token.executive_id)
        if id is not None:
            query = query.filter(ExecutiveToken.id == id)
        if id_ge is not None:
            query = query.filter(ExecutiveToken.id >= id_ge)
        if id_le is not None:
            query = query.filter(ExecutiveToken.id <= id_le)
        if platform_type is not None:
            query = query.filter(ExecutiveToken.platform_type == platform_type)
        if client_details is not None:
            query = query.filter(
                ExecutiveToken.client_details.ilike(f"%{client_details}%")
            )
        if created_on is not None:
            query = query.filter(ExecutiveToken.created_on == created_on)
        if created_on_ge is not None:
            query = query.filter(ExecutiveToken.created_on >= created_on_ge)
        if created_on_le is not None:
            query = query.filter(ExecutiveToken.created_on <= created_on_le)

        # Apply ordering
        orderQuery = getattr(ExecutiveToken, OrderBy(order_by).name)
        if order_in == OrderIn.ASC:
            query = query.order_by(orderQuery.asc())
        query = query.order_by(orderQuery.desc())

        tokens = query.limit(limit).offset(offset).all()
        return tokens
    except Exception as e:
        exceptions.handle(e)
    finally:
        session.close()


@route_executive.delete("/entebus/account/token", tags=["Token"])
async def delete_tokens(credential=Depends(bearer_executive)):
    pass
