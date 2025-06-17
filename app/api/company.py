from typing import Annotated
from fastapi import APIRouter, Depends, Form, status
from fastapi.encoders import jsonable_encoder
from pydantic_extra_types.phone_numbers import PhoneNumber
from pydantic import EmailStr
from shapely.geometry import Point
from sqlalchemy import func
from app.src.constants import EPSG_4326

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
    id: Annotated[int, Form()],
    name: Annotated[str | None, Form(min_length=4, max_length=32)] = None,
    address: Annotated[str | None, Form(min_length=4, max_length=512)] = None,
    location: Annotated[str | None, Form()] = None,
    contact_person: Annotated[str | None, Form(min_length=4, max_length=32)] = None,
    phone_number: Annotated[PhoneNumber | None, Form()] = None,
    email_id: Annotated[EmailStr | None, Form()] = None,
    status: Annotated[CompanyStatus | None, Form()] = None,
    type: Annotated[CompanyType | None, Form()] = None,
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

        company = session.query(Company).filter(Company.id == id).first()
        if company is None:
            raise exceptions.InvalidIdentifier()

        if name is not None and company.name != name:
            company.name = name
        if address is not None and company.address != address:
            company.address = address
        if contact_person is not None and company.contact_person != contact_person:
            company.contact_person = contact_person
        if phone_number is not None and company.phone_number != str(phone_number):
            company.phone_number = str(phone_number)
        if email_id is not None and company.email_id != email_id:
            company.email_id = email_id
        if status is not None and company.status != status:
            company.status = status
        if type is not None and company.type != type:
            company.type = type

        if location is not None:
            wkt_location = toWKTgeometry(location, Point)
            if wkt_location is None:
                raise exceptions.InvalidWKTStringOrType()
            if not isSRID4326(wkt_location):
                raise exceptions.InvalidSRID4326()

            current_location = session.scalar(func.ST_AsText(company.location))
            if current_location != location:
                company.location = func.ST_SetSRID(
                    func.ST_GeomFromText(location), EPSG_4326
                )

        if session.is_modified(company):
            session.commit()
            session.refresh(company)

            log_data = jsonable_encoder(company, exclude={"location"})
            log_data["location"] = session.scalar(func.ST_AsText(company.location))
            logExecutiveEvent(token, request_info, log_data)
            return log_data
        else:
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
    Allows an operator to update their company's contact and location details.

    - Accepts optional updates to contact info, address, and location (WKT).
    - Operators **cannot** update name or status.
    - Validates WKT and SRID 4326 for location.
    - Falls back to authenticated company if no ID is provided.
    - Rejects updates to other companies' data.
    """,
)
async def update_company(
    id: Annotated[int | None, Form()] = None,
    contact_person: Annotated[str | None, Form(min_length=4, max_length=32)] = None,
    location: Annotated[str | None, Form()] = None,
    phone_number: Annotated[PhoneNumber | None, Form()] = None,
    email_id: Annotated[EmailStr | None, Form()] = None,
    address: Annotated[str | None, Form(min_length=4, max_length=512)] = None,
    bearer=Depends(bearer_operator),
    request_info=Depends(getRequestInfo),
):
    try:
        session = sessionMaker()
        token = getOperatorToken(bearer.credentials, session)
        if token is None:
            raise exceptions.InvalidToken()

        role = getOperatorRole(token, session)
        if not role or not role.update_company:
            raise exceptions.NoPermission()

        operator_company_id = token.company_id
        target_company_id = id if id is not None else operator_company_id

        company = session.query(Company).filter(Company.id == target_company_id).first()
        if company is None or company.id != operator_company_id:
            raise exceptions.InvalidIdentifier()

        if contact_person is not None and company.contact_person != contact_person:
            company.contact_person = contact_person
        if phone_number is not None and company.phone_number != str(phone_number):
            company.phone_number = str(phone_number)
        if email_id is not None and company.email_id != email_id:
            company.email_id = email_id
        if address is not None and company.address != address:
            company.address = address

        if location is not None:
            wkt_location = toWKTgeometry(location, Point)
            if wkt_location is None:
                raise exceptions.InvalidWKTStringOrType()
            if not isSRID4326(wkt_location):
                raise exceptions.InvalidSRID4326()

            current_location = session.scalar(func.ST_AsText(company.location))
            if current_location != location:
                company.location = func.ST_SetSRID(
                    func.ST_GeomFromText(location), EPSG_4326
                )

        if session.is_modified(company):
            session.commit()
            session.refresh(company)

            log_data = jsonable_encoder(company, exclude={"location"})
            log_data["location"] = session.scalar(func.ST_AsText(company.location))
            logOperatorEvent(token, request_info, log_data)
            return log_data
        else:
            company_data = jsonable_encoder(company, exclude={"location"})
            company_data["location"] = session.scalar(func.ST_AsText(company.location))
            session.expunge(company)
            return company_data

    except Exception as e:
        exceptions.handle(e)
    finally:
        session.close()
