from typing import Annotated
from fastapi import APIRouter, Depends, Form, status
from fastapi.encoders import jsonable_encoder
from pydantic_extra_types.phone_numbers import PhoneNumber
from pydantic import EmailStr
from shapely.geometry import Point

from app.api.bearer import bearer_executive
from app.src import schemas, exceptions
from app.src.db import sessionMaker, Business, BusinessWallet
from app.src.enums import BusinessStatus, BusinessType
from app.src.functions import (
    enumStr,
    getExecutiveRole,
    getExecutiveToken,
    getRequestInfo,
    isSRID4326,
    logExecutiveEvent,
    makeExceptionResponses,
    toWKTgeometry,
)

route_executive = APIRouter()


@route_executive.post(
    "/business",
    tags=["Business"],
    response_model=schemas.Business,
    status_code=status.HTTP_201_CREATED,
    responses=makeExceptionResponses(
        [
            exceptions.InvalidToken,
            exceptions.NoPermission,
            exceptions.InvalidWKTStringOrType,
            exceptions.InvalidSRID4326,
        ]
    ),
    description="""
    Creating a new business with a location, address, and website is optional.

    - Accepts an optional WKT **POINT** representing the business's location.
    - If provided, validates geometry format and SRID compliance (must be 4326).
    - Requires executives to have `create_business` permission.
    - Ensures business **phone number** and **email** are unique.
    - Logs the business creation event tied to the authenticated executive.
    """,
)
async def create_business(
    name: Annotated[str, Form(min_length=4, max_length=32)],
    contact_person: Annotated[str, Form(min_length=4, max_length=64)],
    phone_number: Annotated[PhoneNumber, Form()],
    email_id: Annotated[EmailStr, Form()],
    address: Annotated[str | None, Form(min_length=4, max_length=512)] = None,
    location: Annotated[
        str | None, Form(description="Optional WKT POINT with SRID 4326")
    ] = None,
    website: Annotated[str | None, Form()] = None,
    status: Annotated[
        BusinessStatus, Form(description=enumStr(BusinessStatus))
    ] = BusinessStatus.ACTIVE,
    type: Annotated[
        BusinessType, Form(description=enumStr(BusinessType))
    ] = BusinessType.OTHER,
    bearer=Depends(bearer_executive),
    request_info=Depends(getRequestInfo),
):
    try:
        session = sessionMaker()
        token = getExecutiveToken(bearer.credentials, session)
        if token is None:
            raise exceptions.InvalidToken()
        role = getExecutiveRole(token, session)
        if not role or not role.create_business:
            raise exceptions.NoPermission()

        if location is not None:
            wktLocation = toWKTgeometry(location, Point)
            if wktLocation is None:
                raise exceptions.InvalidWKTStringOrType()
            if not isSRID4326(wktLocation):
                raise exceptions.InvalidSRID4326()

        business = Business(
            name=name,
            contact_person=contact_person,
            phone_number=phone_number,
            email_id=email_id,
            address=address,
            location=location,
            website=website,
            status=status,
            type=type,
        )
        session.add(business)
        session.commit()
        logExecutiveEvent(token, request_info, jsonable_encoder(business))
        return business
    finally:
        session.close()


# Business Wallet
@route_executive.post(
    "/business_wallet",
    tags=["BusinessWallet"],
    response_model=schemas.BusinessWallet,
    status_code=status.HTTP_201_CREATED,
    responses=makeExceptionResponses(
        [
            exceptions.InvalidToken,
            exceptions.NoPermission,
            exceptions.WalletAlreadyExists,
        ]
    ),
    description="""
    Creates a business wallet.

    - Requires a valid access token with `create_business_wallet` permission.
    - Logs the wallet creation event tied to the authenticated business.
    - One business can have one wallet.
    """,
)
async def create_wallet(
    business_id: Annotated[int, Form()],
    account_number: Annotated[str, Form(min_length=9, max_length=32)],
    account_name: Annotated[str, Form(min_length=4, max_length=64)],
    ifsc_code: Annotated[str, Form(min_length=11, max_length=16)],
    balance: Annotated[int, Form()],
    bank_name: Annotated[str | None, Form(min_length=4, max_length=64)] = None,
    bearer=Depends(bearer_executive),
    request_info=Depends(getRequestInfo),
):
    try:
        session = sessionMaker()
        token = getExecutiveToken(bearer.credentials, session)

        if token is None:
            raise exceptions.InvalidToken()
        role = getExecutiveRole(token, session)
        canCreateWallet = bool(role and role.create_executive)
        if not canCreateWallet:
            raise exceptions.NoPermission()

        existing_wallet = (
            session.query(BusinessWallet).filter_by(business_id=business_id).first()
        )
        if existing_wallet:
            raise exceptions.WalletAlreadyExists()

        business_wallet = BusinessWallet(
            business_id=business_id,
            account_number=account_number,
            account_name=account_name,
            ifsc_code=ifsc_code,
            balance=balance,
            bank_name=bank_name,
        )
        session.add(business_wallet)
        session.commit()
        logExecutiveEvent(token, request_info, jsonable_encoder(business_wallet))
        return business_wallet
    except Exception as e:
        exceptions.handle(e)
    finally:
        session.close()
