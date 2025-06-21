from typing import Annotated
from fastapi import APIRouter, Depends, Form, status
from fastapi.encoders import jsonable_encoder
from pydantic_extra_types.phone_numbers import PhoneNumber
from pydantic import EmailStr
from shapely.geometry import Point
from typing import Annotated, Optional

from app.api.bearer import bearer_executive
from app.src import schemas, exceptions
from app.src.db import sessionMaker, Company, CompanyWallet
from app.src.enums import CompanyStatus, CompanyType
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


## API endpoints [Executive]
@route_executive.post(
    "/company",
    tags=["Company"],
    response_model=schemas.Company,
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
    Creates a new company with geospatial point location using SRID 4326 (WGS84).

    - Accepts a WKT **POINT** representing the company's location.
    - Validates geometry format and SRID compliance (must be 4326).
    - Requires executives to have `create_company` permission.
    - Ensures company **name** and **phone number** are unique in the system.
    - Logs the company creation event tied to the authenticated executive.
    """,
)
async def create_company(
    name: Annotated[str, Form(min_length=4, max_length=32)],
    address: Annotated[str, Form(min_length=4, max_length=512)],
    location: Annotated[str, Form(description="Accepts only SRID 4326 (WGS84)")],
    contact_person: Annotated[str, Form(min_length=4, max_length=32)],
    phone_number: Annotated[PhoneNumber, Form()],
    email_id: Annotated[Optional[EmailStr], Form()] = None,
    status: Annotated[
        CompanyStatus, Form(description=enumStr(CompanyStatus))
    ] = CompanyStatus.UNDER_VERIFICATION,
    type: Annotated[
        CompanyType, Form(description=enumStr(CompanyType))
    ] = CompanyType.PRIVATE,
    bearer=Depends(bearer_executive),
    request_info=Depends(getRequestInfo),
):
    try:
        session = sessionMaker()
        token = getExecutiveToken(bearer.credentials, session)
        if token is None:
            raise exceptions.InvalidToken()
        role = getExecutiveRole(token, session)
        if not role or not role.create_company:
            raise exceptions.NoPermission()

        wktLocation = toWKTgeometry(location, Point)
        if wktLocation is None:
            raise exceptions.InvalidWKTStringOrType()
        if not isSRID4326(wktLocation):
            raise exceptions.InvalidSRID4326()

        company = Company(
            name=name,
            address=address,
            location=location,
            contact_person=contact_person,
            phone_number=phone_number,
            email_id=email_id,
            status=status,
            type=type,
        )
        session.add(company)
        session.commit()
        logExecutiveEvent(token, request_info, jsonable_encoder(company))
        return company
    except Exception as e:
        exceptions.handle(e)
    finally:
        session.close()


# Company Wallet
@route_executive.post(
    "/company_wallet",
    tags=["CompanyWallet"],
    response_model=schemas.CompanyWallet,
    status_code=status.HTTP_201_CREATED,
    responses=makeExceptionResponses(
        [
            exceptions.InvalidToken,
            exceptions.NoPermission,
            exceptions.WalletAlreadyExists,
        ]
    ),
    description="""
    Creates a company wallet.

    - Requires a valid access token with `create_company_wallet` permission.
    - Logs the wallet creation event tied to the authenticated company.
    - One company can have one wallet.
    """,
)
async def create_wallet(
    company_id: Annotated[int, Form()],
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
            session.query(CompanyWallet).filter_by(company_id=company_id).first()
        )
        if existing_wallet:
            raise exceptions.WalletAlreadyExists()

        company_wallet = CompanyWallet(
            company_id=company_id,
            account_number=account_number,
            account_name=account_name,
            ifsc_code=ifsc_code,
            balance=balance,
            bank_name=bank_name,
        )
        session.add(company_wallet)
        session.commit()
        logExecutiveEvent(token, request_info, jsonable_encoder(company_wallet))
        return company_wallet
    except Exception as e:
        exceptions.handle(e)
    finally:
        session.close()
