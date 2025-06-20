from typing import Annotated, Optional
from fastapi import APIRouter, Depends, Form, status
from fastapi.encoders import jsonable_encoder
from pydantic import BaseModel, Field
from pydantic_extra_types.phone_numbers import PhoneNumber
from pydantic import EmailStr
from shapely.geometry import Point
from sqlalchemy import func
from app.src.constants import EPSG_4326
from shapely import wkt
from sqlalchemy.orm.session import Session

from app.api.bearer import bearer_executive, bearer_operator
from app.src import schemas, exceptions
from app.src.db import sessionMaker, Company
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
    getOperatorRole,
    getOperatorToken,
    logOperatorEvent,
)

route_executive = APIRouter()
route_operator = APIRouter()


class UpdateFormForExecutive(BaseModel):
    id: int = Field(Form())
    name: str | None = Field(Form(min_length=4, max_length=32, default=None))
    address: str | None = Field(Form(min_length=4, max_length=512, default=None))
    location: str | None = Field(Form(default=None))
    contact_person: str | None = Field(Form(min_length=4, max_length=32, default=None))
    phone_number: PhoneNumber | None = Field(Form(default=None))
    email_id: EmailStr | None = Field(Form(default=None))
    status: CompanyStatus | None = Field(Form(default=None))
    type: CompanyType | None = Field(Form(default=None))


## Function
def updateExecutiveCompany(
    session: Session, company: Company, fParam: UpdateFormForExecutive
) -> bool:
    is_modified = False

    if fParam.name is not None and company.name != fParam.name:
        company.name = fParam.name
        is_modified = True

    if fParam.address is not None and company.address != fParam.address:
        company.address = fParam.address
        is_modified = True

    if (
        fParam.contact_person is not None
        and company.contact_person != fParam.contact_person
    ):
        company.contact_person = fParam.contact_person
        is_modified = True

    if fParam.phone_number is not None and company.phone_number != str(
        fParam.phone_number
    ):
        company.phone_number = str(fParam.phone_number)
        is_modified = True

    if fParam.email_id is not None and company.email_id != fParam.email_id:
        company.email_id = fParam.email_id
        is_modified = True

    if fParam.status is not None and company.status != fParam.status:
        company.status = fParam.status
        is_modified = True

    if fParam.type is not None and company.type != fParam.type:
        company.type = fParam.type
        is_modified = True

    if fParam.location is not None:
        wkt_location = toWKTgeometry(fParam.location, Point)
        if wkt_location is None:
            raise exceptions.InvalidWKTStringOrType()
        if not isSRID4326(wkt_location):
            raise exceptions.InvalidSRID4326()

        current_location = session.scalar(func.ST_AsText(company.location))
        if current_location != fParam.location:
            company.location = func.ST_SetSRID(
                func.ST_GeomFromText(fParam.location), EPSG_4326
            )
            is_modified = True

    return is_modified


class UpdateFormForOperator(BaseModel):
    id: int | None = Field(Form(default=None))
    contact_person: str | None = Field(Form(min_length=4, max_length=32, default=None))
    location: str | None = Field(Form(default=None))
    phone_number: PhoneNumber | None = Field(Form(default=None))
    email_id: EmailStr | None = Field(Form(default=None))
    address: str | None = Field(Form(min_length=4, max_length=512, default=None))


## Function
def updateOperatorCompany(
    session: Session, company: Company, fParam: UpdateFormForOperator
) -> bool:
    is_modified = False

    if (
        fParam.contact_person is not None
        and company.contact_person != fParam.contact_person
    ):
        company.contact_person = fParam.contact_person
        is_modified = True

    if fParam.phone_number is not None and company.phone_number != str(
        fParam.phone_number
    ):
        company.phone_number = str(fParam.phone_number)
        is_modified = True

    if fParam.email_id is not None and company.email_id != fParam.email_id:
        company.email_id = fParam.email_id
        is_modified = True

    if fParam.address is not None and company.address != fParam.address:
        company.address = fParam.address
        is_modified = True

    if fParam.location is not None:
        wkt_location = toWKTgeometry(fParam.location, Point)
        if wkt_location is None:
            raise exceptions.InvalidWKTStringOrType()
        if not isSRID4326(wkt_location):
            raise exceptions.InvalidSRID4326()
        current_location = session.scalar(func.ST_AsText(company.location))
        if current_location != fParam.location:
            company.location = func.ST_SetSRID(
                func.ST_GeomFromText(fParam.location), EPSG_4326
            )
            is_modified = True

    return is_modified


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
    email_id: Annotated[EmailStr | None, Form()] = None,
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


@route_executive.patch(
    "/company",
    tags=["Company"],
    response_model=schemas.Company,
    responses=makeExceptionResponses(
        [
            exceptions.InvalidToken,
            exceptions.NoPermission,
            exceptions.InvalidIdentifier,
            exceptions.InvalidWKTStringOrType,
            exceptions.InvalidSRID4326,
        ]
    ),
    description="""
    Updates an existing company with permission.

    - Accepts optional updates to name, address, contact details, type, status, and location (WKT).
    - Validates location as a WKT **POINT** with SRID 4326.
    - Requires executives to have `update_company` permission.
    - Logs updates only if any field was changed.
    """,
)
async def update_company(
    fParam: UpdateFormForExecutive = Depends(),
    bearer=Depends(bearer_executive),
    request_info=Depends(getRequestInfo),
):
    try:
        session = sessionMaker()
        token = getExecutiveToken(bearer.credentials, session)
        if token is None:
            raise exceptions.InvalidToken()

        role = getExecutiveRole(token, session)
        if not role or not role.update_company:
            raise exceptions.NoPermission()

        company = session.query(Company).filter(Company.id == fParam.id).first()
        if company is None:
            raise exceptions.InvalidIdentifier()

        is_modified = updateExecutiveCompany(session, company, fParam)

        if is_modified:
            session.commit()
            session.refresh(company)
            log_data = jsonable_encoder(company, exclude={"location"})
            log_data["location"] = session.scalar(func.ST_AsText(company.location))
            logExecutiveEvent(token, request_info, log_data)
            return log_data

        company_data = jsonable_encoder(company, exclude={"location"})
        company_data["location"] = session.scalar(func.ST_AsText(company.location))
        session.expunge(company)
        return company_data

    except Exception as e:
        exceptions.handle(e)
    finally:
        session.close()


## API endpoints [Operator]
@route_operator.patch(
    "/company",
    tags=["Company"],
    response_model=schemas.Company,
    responses=makeExceptionResponses(
        [
            exceptions.InvalidToken,
            exceptions.NoPermission,
            exceptions.InvalidIdentifier,
            exceptions.InvalidWKTStringOrType,
            exceptions.InvalidSRID4326,
        ]
    ),
    description="""
    Allows an operator to update their company's contact, address, location.

    - Partial updates allowed for contact info, address, WKT location.
    - Operators cannot alter name or status.
    - Validates WKT format and SRID 4326.
    - Uses authenticated operator's company if no ID is provided.
    - Rejects updates to other operators' companies.
    """,
)
async def update_company(
    fParam: UpdateFormForOperator = Depends(),
    bearer=Depends(bearer_operator),
    request_info=Depends(getRequestInfo),
):
    try:
        session = sessionMaker()
        token = getOperatorToken(bearer.credentials, session)
        if token is None:
            raise exceptions.InvalidToken()

        role = getOperatorRole(token, session)
        if not (role and role.create_company):
            raise exceptions.NoPermission()

        operator_company_id = token.company_id
        target_id = fParam.id or operator_company_id

        company = session.query(Company).filter(Company.id == target_id).first()
        if not company or company.id != operator_company_id:
            raise exceptions.InvalidIdentifier()

        modified = updateOperatorCompany(session, company, fParam)

        if modified:
            session.commit()
            session.refresh(company)
            log_data = jsonable_encoder(company, exclude={"location"})
            log_data["location"] = session.scalar(func.ST_AsText(company.location))
            logOperatorEvent(token, request_info, log_data)
            return log_data
        company_data = jsonable_encoder(company, exclude={"location"})
        company_data["location"] = session.scalar(func.ST_AsText(company.location))
        session.expunge(company)
        return company_data

    except Exception as e:
        exceptions.handle(e)
    finally:
        session.close()
