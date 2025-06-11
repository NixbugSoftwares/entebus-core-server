from enum import IntEnum
from sqlalchemy.orm.session import Session
from fastapi import (
    APIRouter,
    Depends,
    Query,
    status,
    Form,
    Response,
)
from typing import Annotated, List, Optional
from fastapi.encoders import jsonable_encoder
from datetime import datetime, timedelta, timezone
from pydantic import BaseModel, Field

from app.api.bearer import bearer_executive, bearer_operator
from app.src import argon2, exceptions
from app.src.constants import MAX_OPERATOR_TOKENS, MAX_TOKEN_VALIDITY
from app.src.enums import AccountStatus, OrderIn, PlatformType
from app.src import schemas
from app.src.db import (
    sessionMaker,
    Operator,
    OperatorToken,
)
from app.src.functions import (
    enumStr,
    getExecutiveRole,
    getExecutiveToken,
    getOperatorRole,
    getOperatorToken,
    getRequestInfo,
    logOperatorEvent,
    makeExceptionResponses,
    getOperatorToken,
    getOperatorRole,
    getExecutiveToken,
    getExecutiveRole,
    logExecutiveEvent,
)

route_operator = APIRouter()
route_executive = APIRouter()


## Schemas
class OrderBy(IntEnum):
    id = 1
    created_on = 2


class OperatorTokenQueryParams(BaseModel):
    id: Optional[int] = None
    id_ge: Optional[int] = None
    id_le: Optional[int] = None
    operator_id: Optional[int] = None
    platform_type: Optional[PlatformType] = Field(
        Query(default=None, description=enumStr(PlatformType))
    )
    client_details: Optional[str] = None
    created_on: Optional[datetime] = None
    created_on_ge: Optional[datetime] = None
    created_on_le: Optional[datetime] = None
    offset: int = Query(default=0, ge=0)
    limit: int = Query(default=20, gt=0, le=100)
    order_by: OrderBy = Field(Query(default=OrderBy.id, description=enumStr(OrderBy)))
    order_in: OrderIn = Field(Query(default=OrderIn.DESC, description=enumStr(OrderIn)))


class ExecutiveTokenQueryParams(OperatorTokenQueryParams):
    company_id: Optional[int] = None


## Function
def queryOperatorTokens(
    session: Session, qParam: ExecutiveTokenQueryParams
) -> List[OperatorToken]:
    query = session.query(OperatorToken)
    if qParam.company_id is not None:
        query = query.filter(OperatorToken.company_id == qParam.company_id)
    if qParam.operator_id is not None:
        query = query.filter(OperatorToken.operator_id == qParam.operator_id)
    if qParam.id is not None:
        query = query.filter(OperatorToken.id == qParam.id)
    if qParam.id_ge is not None:
        query = query.filter(OperatorToken.id >= qParam.id_ge)
    if qParam.id_le is not None:
        query = query.filter(OperatorToken.id <= qParam.id_le)
    if qParam.platform_type is not None:
        query = query.filter(OperatorToken.platform_type == qParam.platform_type)
    if qParam.client_details is not None:
        query = query.filter(
            OperatorToken.client_details.ilike(f"%{qParam.client_details}%")
        )
    if qParam.created_on is not None:
        query = query.filter(OperatorToken.created_on == qParam.created_on)
    if qParam.created_on_ge is not None:
        query = query.filter(OperatorToken.created_on >= qParam.created_on_ge)
    if qParam.created_on_le is not None:
        query = query.filter(OperatorToken.created_on <= qParam.created_on_le)

    # Apply ordering
    orderQuery = getattr(OperatorToken, OrderBy(qParam.order_by).name)
    if qParam.order_in == OrderIn.ASC:
        query = query.order_by(orderQuery.asc())
    else:
        query = query.order_by(orderQuery.desc())
    return query.limit(qParam.limit).offset(qParam.offset).all()


## API endpoints [Operator]
@route_operator.post(
    "/company/account/token",
    tags=["Token"],
    response_model=schemas.OperatorToken,
    status_code=status.HTTP_201_CREATED,
    responses=makeExceptionResponses(
        [exceptions.InactiveAccount, exceptions.InvalidCredentials]
    ),
    description="""
    Issues a new access token for an operator after validating credentials.

    - This endpoint performs authentication using company_id, username and password submitted as form data. 
    - If the credentials are valid and the operator account is active, a new token is generated and returned.
    - Limits active tokens using MAX_OPERATOR_TOKENS (token rotation).
    - Sets expiration with expires_in=MAX_TOKEN_VALIDITY (in seconds).
    - Token will be generated for ACTIVE operators only.
    - Logs the authentication event for audit tracking.
    """,
)
async def create_token(
    company_id: Annotated[int, Form()],
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
        operator = (
            session.query(Operator)
            .filter(Operator.username == username)
            .filter(Operator.company_id == company_id)
            .first()
        )
        if operator is None:
            raise exceptions.InvalidCredentials()

        if not argon2.checkPassword(password, operator.password):
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
            company_id=company_id,
            operator_id=operator.id,
            expires_in=MAX_TOKEN_VALIDITY,
            expires_at=expires_at,
            platform_type=platform_type,
            client_details=client_details,
        )
        session.add(token)
        session.commit()
        logOperatorEvent(
            token, request_info, jsonable_encoder(token, exclude={"access_token"})
        )
        return token
    except Exception as e:
        exceptions.handle(e)
    finally:
        session.close()


@route_operator.patch("/company/account/token", tags=["Token"])
async def update_token(credential=Depends(bearer_operator)):
    pass


@route_operator.get(
    "/company/account/token",
    tags=["Token"],
    response_model=List[schemas.MaskedOperatorToken],
    responses=makeExceptionResponses([exceptions.InvalidToken]),
    description="""
    Fetches a list of operator tokens filtered by optional query parameters.
    
    - Operators without `manage_op_token` permission can only retrieve their own tokens.
    - Supports filtering by ID range, platform type, client details, and creation timestamps.
    - Supports pagination with `offset` and `limit`.
    - Supports sorting using `order_by` and `order_in`.
    """,
)
async def fetch_tokens(
    qParam: OperatorTokenQueryParams = Depends(), bearer=Depends(bearer_operator)
):
    try:
        session = sessionMaker()
        token = getOperatorToken(bearer.credentials, session)
        if token is None:
            raise exceptions.InvalidToken()
        role = getOperatorRole(token, session)
        canManageToken = bool(role and role.manage_op_token)

        qParam = ExecutiveTokenQueryParams(**qParam.model_dump())
        qParam.company_id = token.company_id
        if not canManageToken:
            qParam.operator_id = token.operator_id
        return queryOperatorTokens(session, qParam)
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

    - This endpoint deletes an access token based on the token ID (optional).
    - If no ID is provided, it deletes the token used in the request (self-revocation).
    - If an ID is provided, the caller must either: 
        Own the token being deleted, or have a role with `manage_op_token` permission.
    - If the token ID is invalid or already deleted, the operation is silently ignored.
    - Returns 204 No Content upon success.
    - Logs the token revocation event for audit tracking.
    """,
)
async def delete_token(
    id: Annotated[int | None, Form()] = None,
    bearer=Depends(bearer_operator),
    request_info=Depends(getRequestInfo),
):
    try:
        session = sessionMaker()
        token = getOperatorToken(bearer.credentials, session)
        if token is None:
            raise exceptions.InvalidToken()
        role = getOperatorRole(token, session)

        if id is None:
            tokenToDelete = token
        else:
            tokenToDelete = (
                session.query(OperatorToken)
                .filter(OperatorToken.id == id)
                .filter(OperatorToken.company_id == token.company_id)
                .first()
            )
            if tokenToDelete is not None:
                forSelf = token.operator_id == tokenToDelete.operator_id
                canManageToken = bool(role and role.manage_op_token)
                if not forSelf and not canManageToken:
                    raise exceptions.NoPermission()
            else:
                return Response(status_code=status.HTTP_204_NO_CONTENT)

        session.delete(tokenToDelete)
        session.commit()
        logOperatorEvent(
            token,
            request_info,
            jsonable_encoder(tokenToDelete, exclude={"access_token"}),
        )
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    except Exception as e:
        exceptions.handle(e)
    finally:
        session.close()


## API endpoints [Executive]
@route_executive.get("/company/account/token", tags=["Operator token"])
async def fetch_tokens(credential=Depends(bearer_executive)):
    pass


@route_executive.delete(
    "/company/account/token",
    tags=["Operator token"],
    status_code=status.HTTP_204_NO_CONTENT,
    responses=makeExceptionResponses(
        [exceptions.InvalidToken, exceptions.NoPermission]
    ),
    description="""
    Revokes an access token associated with an operator account.

    - This endpoint deletes an access token based on the operator token ID.
    - The executive with `manage_op_token` permission can delete any operator's token.
    - If the token ID is invalid or already deleted, the operation is silently ignored.
    - Returns 204 No Content upon success.
    - Logs the token revocation event for audit tracking if the id is valid.
    - Requires the operator token ID as an input parameter.
    """,
)
async def delete_token(
    id: Annotated[int, Form()],
    bearer=Depends(bearer_executive),
    request_info=Depends(getRequestInfo),
):
    try:
        session = sessionMaker()
        token = getExecutiveToken(bearer.credentials, session)
        if token is None:
            raise exceptions.InvalidToken()
        role = getExecutiveRole(token, session)
        canManageToken = bool(role and role.manage_op_token)
        if not canManageToken:
            raise exceptions.NoPermission()

        tokenToDelete = (
            session.query(OperatorToken).filter(OperatorToken.id == id).first()
        )
        if tokenToDelete is None:
            return Response(status_code=status.HTTP_204_NO_CONTENT)

        session.delete(tokenToDelete)
        session.commit()
        logExecutiveEvent(
            token,
            request_info,
            jsonable_encoder(tokenToDelete, exclude={"access_token"}),
        )
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    except Exception as e:
        exceptions.handle(e)
    finally:
        session.close()
