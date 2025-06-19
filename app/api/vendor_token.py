from enum import IntEnum
from sqlalchemy.orm.session import Session
from fastapi import (
    APIRouter,
    Depends,
    status,
    Form,
    Query,
)
from typing import Annotated, List
from secrets import token_hex
from fastapi.encoders import jsonable_encoder
from datetime import datetime, timedelta, timezone

from app.api.bearer import bearer_executive, bearer_vendor
from app.src import argon2, exceptions, schemas
from app.src.constants import MAX_VENDOR_TOKENS, MAX_TOKEN_VALIDITY
from app.src.enums import AccountStatus, PlatformType, OrderIn
from pydantic import BaseModel, Field
from app.src.db import (
    sessionMaker,
    Vendor,
    VendorToken,
)
from app.src.functions import (
    enumStr,
    getRequestInfo,
    getVendorToken,
    getVendorRole,
    logVendorEvent,
    getExecutiveToken,
    getExecutiveRole,
    makeExceptionResponses,
)

route_vendor = APIRouter()
route_executive = APIRouter()


## Schemas
class OrderBy(IntEnum):
    id = 1
    created_on = 2
    updated_on = 3


class VendorTokenQueryParams(BaseModel):
    id: int | None = Query(default=None)
    id_ge: int | None = Query(default=None)
    id_le: int | None = Query(default=None)
    vendor_id: int | None = Query(default=None)
    platform_type: PlatformType | None = Field(
        Query(default=None, description=enumStr(PlatformType))
    )
    client_details: str | None = Query(default=None)
    created_on: datetime | None = Query(default=None)
    created_on_ge: datetime | None = Query(default=None)
    created_on_le: datetime | None = Query(default=None)
    updated_on: datetime | None = Query(default=None)
    updated_on_ge: datetime | None = Query(default=None)
    updated_on_le: datetime | None = Query(default=None)
    offset: int = Query(default=0, ge=0)
    limit: int = Query(default=20, gt=0, le=100)
    order_by: OrderBy = Field(Query(default=OrderBy.id, description=enumStr(OrderBy)))
    order_in: OrderIn = Field(Query(default=OrderIn.DESC, description=enumStr(OrderIn)))


class VendorTokenQueryParamsForEx(VendorTokenQueryParams):
    business_id: int | None = Query(default=None)


## Function
def queryVendorTokens(
    session: Session, qParam: VendorTokenQueryParamsForEx
) -> List[VendorToken]:
    query = session.query(VendorToken)
    if qParam.business_id is not None:
        query = query.filter(VendorToken.business_id == qParam.business_id)
    if qParam.vendor_id is not None:
        query = query.filter(VendorToken.vendor_id == qParam.vendor_id)
    if qParam.id is not None:
        query = query.filter(VendorToken.id == qParam.id)
    if qParam.id_ge is not None:
        query = query.filter(VendorToken.id >= qParam.id_ge)
    if qParam.id_le is not None:
        query = query.filter(VendorToken.id <= qParam.id_le)
    if qParam.platform_type is not None:
        query = query.filter(VendorToken.platform_type == qParam.platform_type)
    if qParam.client_details is not None:
        query = query.filter(
            VendorToken.client_details.ilike(f"%{qParam.client_details}%")
        )
    if qParam.created_on is not None:
        query = query.filter(VendorToken.created_on == qParam.created_on)
    if qParam.created_on_ge is not None:
        query = query.filter(VendorToken.created_on >= qParam.created_on_ge)
    if qParam.created_on_le is not None:
        query = query.filter(VendorToken.created_on <= qParam.created_on_le)
    if qParam.updated_on is not None:
        query = query.filter(VendorToken.updated_on == qParam.updated_on)
    if qParam.updated_on_ge is not None:
        query = query.filter(VendorToken.updated_on >= qParam.updated_on_ge)
    if qParam.updated_on_le is not None:
        query = query.filter(VendorToken.updated_on <= qParam.updated_on_le)

    # Apply ordering
    orderQuery = getattr(VendorToken, OrderBy(qParam.order_by).name)
    if qParam.order_in == OrderIn.ASC:
        query = query.order_by(orderQuery.asc())
    else:
        query = query.order_by(orderQuery.desc())
    return query.limit(qParam.limit).offset(qParam.offset).all()


## API endpoints [Vendor]
@route_vendor.post(
    "/business/account/token",
    tags=["Token"],
    response_model=schemas.VendorToken,
    status_code=status.HTTP_201_CREATED,
    responses=makeExceptionResponses(
        [exceptions.InactiveAccount, exceptions.InvalidCredentials]
    ),
    description="""
    Issues a new access token for an vendor after validating credentials.

    - Accepts form data including the vendor's `business_id`, `username`, and `password` for credential verification.
    - Only vendors with an `ACTIVE` account status are permitted to receive a token.
    - Limits active tokens using `MAX_VENDOR_TOKENS` (token rotation).
    - Generates a token with an expiry time of `MAX_TOKEN_VALIDITY` seconds from creation.
    - Optionally accepts platform type and client details for logging and metadata.
    - Logs authentication events for auditing purposes.
    """,
)
async def token_creation(
    business_id: Annotated[int, Form()],
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
        vendor = (
            session.query(Vendor)
            .filter(Vendor.username == username)
            .filter(Vendor.business_id == business_id)
            .first()
        )
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
            business_id=business_id,
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


@route_vendor.patch(
    "/business/account/token",
    tags=["Token"],
    response_model=schemas.VendorToken,
    responses=makeExceptionResponses(
        [exceptions.InvalidToken, exceptions.NoPermission, exceptions.InvalidIdentifier]
    ),
    description="""
    Refreshes a vendor's existing access token to maintain authenticated access.

    - If `id` is not given, refreshes only the current token (used in this request).
    - If an `id` is provided: Must match the current token's `access_token` (prevents
      unauthorized refreshes, even by the same vendor).
    - Raises `InvalidIdentifier` if the token does not exist (avoids ID probing).
    - Extends `expires_at` by `MAX_TOKEN_VALIDITY` seconds.
    - Rotates the `access_token` value (invalidates the old token immediately).
    - Logs the refresh event for auditability.
    """,
)
async def refresh_token(
    id: Annotated[int | None, Form()] = None,
    bearer=Depends(bearer_vendor),
    request_info=Depends(getRequestInfo),
):
    try:
        session = sessionMaker()
        token = getVendorToken(bearer.credentials, session)

        if id is None:
            tokenToUpdate = token
        else:
            tokenToUpdate = (
                session.query(VendorToken).filter(VendorToken.id == id).first()
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
        logVendorEvent(
            token,
            request_info,
            jsonable_encoder(tokenToUpdate, exclude={"access_token"}),
        )
        session.expunge(tokenToUpdate)
        return tokenToUpdate
    except Exception as e:
        exceptions.handle(e)
    finally:
        session.close()


@route_vendor.get(
    "/business/account/token",
    tags=["Token"],
    response_model=List[schemas.MaskedVendorToken],
    responses=makeExceptionResponses([exceptions.InvalidToken]),
    description="""
    Fetches a list of vendor tokens filtered by optional query parameters.
    
    - Vendors without `manage_token` permission can only retrieve their own tokens.
    - Supports filtering by ID range, platform type, client details, creation timestamps and updating timestamps.
    - Supports pagination with `offset` and `limit`.
    - Supports sorting using `order_by` and `order_in`.
    """,
)
async def fetch_tokens(
    qParam: VendorTokenQueryParams = Depends(), bearer=Depends(bearer_vendor)
):
    try:
        session = sessionMaker()
        token = getVendorToken(bearer.credentials, session)
        if token is None:
            raise exceptions.InvalidToken()
        role = getVendorRole(token, session)
        canManageToken = bool(role and role.manage_token)

        qParam = VendorTokenQueryParamsForEx(**qParam.model_dump())
        qParam.business_id = token.business_id
        if not canManageToken:
            qParam.business_id = token.business_id
        return queryVendorTokens(session, qParam)
    except Exception as e:
        exceptions.handle(e)
    finally:
        session.close()


@route_vendor.delete("/business/account/token", tags=["Token"])
async def delete_tokens(credential=Depends(bearer_vendor)):
    pass


## API endpoints [Executive]
@route_executive.get(
    "/business/account/token",
    tags=["Vendor token"],
    response_model=List[schemas.MaskedVendorToken],
    responses=makeExceptionResponses(
        [exceptions.InvalidToken, exceptions.NoPermission]
    ),
    description=""" 
    Fetches a list of operator tokens belonging to a company, filtered by optional query parameters.

    - Only executives with `manage_ve_token` permission can access this endpoint.
    - Supports filtering by token ID, operator ID, platform type, client details, updating timestamps and creation timestamps.
    - Enables pagination using `offset` and `limit`.
    - Allows sorting using `order_by` and `order_in`.
    """,
)
async def fetch_tokens(
    qParam: VendorTokenQueryParamsForEx = Depends(), bearer=Depends(bearer_executive)
):
    try:
        session = sessionMaker()
        token = getExecutiveToken(bearer.credentials, session)
        if token is None:
            raise exceptions.InvalidToken()
        role = getExecutiveRole(token, session)
        canManageToken = bool(role and role.manage_ve_token)
        if not canManageToken:
            raise exceptions.NoPermission()

        return queryVendorTokens(session, qParam)
    except Exception as e:
        exceptions.handle(e)
    finally:
        session.close()


@route_executive.delete("/business/account/token", tags=["Vendor token"])
async def delete_tokens(credential=Depends(bearer_executive)):
    pass
