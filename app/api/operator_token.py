from fastapi import (
    APIRouter,
    Depends,
    status,
    Form,
    Response,
)
from typing import Annotated
from fastapi.encoders import jsonable_encoder
from datetime import datetime, timedelta, timezone

from app.api.bearer import bearer_executive, bearer_operator
from app.src import argon2, exceptions
from app.src.constants import MAX_OPERATOR_TOKENS, MAX_TOKEN_VALIDITY
from app.src.enums import AccountStatus, PlatformType
from app.src import schemas
from app.src.db import (
    sessionMaker,
    Operator,
    OperatorToken,
)
from app.src.functions import (
    enumStr,
    getRequestInfo,
    logOperatorEvent,
    makeExceptionResponses,
    getOperatorToken,
    getOperatorRole,
)


route_operator = APIRouter()
route_executive = APIRouter()


## API endpoints
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


@route_operator.get("/company/account/token", tags=["Token"])
async def fetch_tokens(credential=Depends(bearer_operator)):
    pass


@route_operator.delete(
    "/company/account/token",
    tags=["Token"],
    status_code=status.HTTP_204_NO_CONTENT,
    responses=makeExceptionResponses(
        [exceptions.InvalidToken, exceptions.NoPermission]
    ),
    description="""
    Revokes an active access token associated with an executive account.

    - This endpoint deletes an access token based on the token ID (optional).
    - If no ID is provided, it deletes the token used in the request (self-revocation).
    - If an ID is provided, the caller must either: 
        Own the token being deleted, or have a role with `manage_ex_token` permission.
    - If the token ID is invalid or already deleted, the operation is silently ignored.
    - Returns 204 No Content upon success.
    - Logs the token revocation event for audit tracking.
    """,
)
async def delete_tokens(
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


@route_executive.get("/company/account/token", tags=["Operator token"])
async def fetch_tokens(credential=Depends(bearer_executive)):
    pass


@route_executive.delete("/company/account/token", tags=["Operator token"])
async def delete_tokens(credential=Depends(bearer_executive)):
    pass
