from typing import Annotated
from fastapi import APIRouter, Depends, Form, status
from fastapi.encoders import jsonable_encoder
from pydantic import BaseModel, Field

from app.api.bearer import bearer_executive
from app.src.constants import MAX_EXECUTIVE_TOKENS, MAX_TOKEN_VALIDITY
from app.src.enums import AccountStatus, PlatformType
from app.src import schemas
from app.src.db import sessionMaker, Executive, ExecutiveToken
from app.src import argon2, exceptions
from app.src.functions import getRequestInfo, logExecutiveEvent, makeExceptionResponses

route_executive = APIRouter()


## Input schemas
class OAuth2Form(BaseModel):
    username: str = Field(..., max_length=32)
    password: str = Field(..., max_length=32)
    platform_type: PlatformType = Field(default=PlatformType.OTHER)
    client_details: str | None = Field(default=None, max_length=1024)


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
    - Limits active tokens using `MAX_EXECUTIVE_TOKENS` (token rotation).
    - Sets expiration with `MAX_TOKEN_VALIDITY`.
    - Logs the authentication event for audit tracking.
    """,
)
async def create_token(
    data: Annotated[OAuth2Form, Form()], request_info=Depends(getRequestInfo)
):
    try:
        session = sessionMaker()
        executive = (
            session.query(Executive).filter(Executive.username == data.username).first()
        )
        if executive is None:
            raise exceptions.InvalidCredentials()

        if not argon2.checkPassword(data.password, executive.password):
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
        token = ExecutiveToken(
            executive_id=executive.id,
            expires_in=MAX_TOKEN_VALIDITY,
            platform_type=data.platform_type,
            client_details=data.client_details,
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


@route_executive.get("/entebus/account/token", tags=["Token"])
async def fetch_tokens(credential=Depends(bearer_executive)):
    pass


@route_executive.delete("/entebus/account/token", tags=["Token"])
async def delete_tokens(credential=Depends(bearer_executive)):
    pass
