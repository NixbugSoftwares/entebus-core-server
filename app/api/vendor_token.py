from fastapi import APIRouter, Depends
from fastapi import (
    APIRouter,
    Depends,
    status,
    Form,
)
from typing import Annotated
from fastapi.encoders import jsonable_encoder
from datetime import datetime, timedelta, timezone
from fastapi.security import OAuth2PasswordRequestForm

from app.api.bearer import bearer_executive, bearer_vendor
from app.src import argon2, exceptions
from app.src.constants import MAX_VENDOR_TOKENS, MAX_TOKEN_VALIDITY
from app.src.enums import AccountStatus, PlatformType
from app.src import schemas
from app.src.db import (
    sessionMaker,
    Vendor,
    VendorToken,
)
from app.src.functions import (
    enumStr,
    getRequestInfo,
    logVendorEvent,
    makeExceptionResponses,
)

route_vendor = APIRouter()
route_executive = APIRouter()


## API endpoints [Vendor]
@route_vendor.post(
    "/vendor/merchant/account",
    tags=["Token"],
    response_model=schemas.VendorToken,
    status_code=status.HTTP_201_CREATED,
    responses=makeExceptionResponses(
        [exceptions.InactiveAccount, exceptions.InvalidCredentials]
    ),
    description="""
    Issues a new access token for an vendor after validating credentials.

    - Accepts OAuth2-style form data for authentication.
    - Only vendors with an `ACTIVE` account status are permitted to receive a token.
    - If authentication fails an appropriate error is returned.
    - Limits active tokens using `MAX_VENDOR_TOKENS` (token rotation).
    - Generates a token with an expiry time of `MAX_TOKEN_VALIDITY` seconds from creation.
    - Optionally accepts platform type and client details for logging and metadata.
    - Logs authentication events for auditing purposes.
    """,
)
async def token_creation(
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
        vendor = session.query(Vendor).filter(Vendor.username == username).first()
        if vendor is None:
            raise exceptions.InvalidCredentials()

        if not argon2.checkPassword(password, vendor.password):
            raise exceptions.InvalidCredentials()
        if vendor.status != AccountStatus.ACTIVE:
            raise exceptions.InactiveAccount()

        # Remove excess tokens from DB
        tokens = (
            session.query(VendorToken)
            .filter(VendorToken.vendor_id == vendor.id)
            .order_by(VendorToken.created_on.desc())
            .all()
        )
        if len(tokens) >= MAX_VENDOR_TOKENS:
            token = tokens[MAX_VENDOR_TOKENS - 1]
            session.delete(token)
            session.flush()

        # Create a new token
        expires_at = datetime.now(timezone.utc) + timedelta(seconds=MAX_TOKEN_VALIDITY)
        token = VendorToken(
            business_id=vendor.business_id,
            vendor_id=vendor.id,
            expires_in=MAX_TOKEN_VALIDITY,
            expires_at=expires_at,
            platform_type=platform_type,
            client_details=client_details,
        )
        session.add(token)
        session.commit()
        logVendorEvent(
            token, request_info, jsonable_encoder(token, exclude={"access_token"})
        )
        return token
    except Exception as e:
        exceptions.handle(e)
    finally:
        session.close()


@route_vendor.patch("/business/account/token", tags=["Token"])
async def update_token(credential=Depends(bearer_vendor)):
    pass


@route_vendor.get("/business/account/token", tags=["Token"])
async def fetch_tokens(credential=Depends(bearer_vendor)):
    pass


@route_vendor.delete("/business/account/token", tags=["Token"])
async def delete_tokens(credential=Depends(bearer_vendor)):
    pass


## API endpoints [Executive]
@route_executive.get("/business/account/token", tags=["Vendor token"])
async def fetch_tokens(credential=Depends(bearer_executive)):
    pass


@route_executive.delete("/business/account/token", tags=["Vendor token"])
async def delete_tokens(credential=Depends(bearer_executive)):
    pass
