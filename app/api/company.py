from datetime import datetime
from enum import IntEnum
from typing import List, Optional
from fastapi import (
    APIRouter,
    Depends,
    Query,
    Response,
    status,
    Form,
)
from sqlalchemy.orm.session import Session
from fastapi.encoders import jsonable_encoder
from pydantic import BaseModel, Field
from pydantic_extra_types.phone_numbers import PhoneNumber
from pydantic import EmailStr
from shapely.geometry import Point
from shapely import wkt, wkb
from sqlalchemy import func
from geoalchemy2 import Geography

from app.api.bearer import bearer_executive, bearer_operator, bearer_vendor
from app.src.db import Company, ExecutiveRole, OperatorRole, sessionMaker
from app.src import exceptions, validators, getters
from app.src.enums import CompanyStatus, CompanyType
from app.src.loggers import logEvent
from app.src.functions import enumStr, makeExceptionResponses

route_executive = APIRouter()
route_vendor = APIRouter()
route_operator = APIRouter()


## Output Schema
class CompanySchemaForVE(BaseModel):
    id: int
    name: str
    type: int
    updated_on: Optional[datetime]
    created_on: datetime


class CompanySchema(CompanySchemaForVE):
    status: int
    address: str
    contact_person: str
    phone_number: str
    email_id: str
    location: str


## Input Forms
class CreateForm(BaseModel):
    name: str = Field(Form(max_length=32))
    status: CompanyStatus = Field(
        Form(
            description=enumStr(CompanyStatus), default=CompanyStatus.UNDER_VERIFICATION
        )
    )
    type: CompanyType = Field(
        Form(description=enumStr(CompanyType), default=CompanyType.OTHER)
    )
    address: str = Field(Form(max_length=512))
    contact_person: str = Field(Form(max_length=32))
    phone_number: PhoneNumber = Field(
        Form(max_length=32, description="Phone number in RFC3966 format")
    )
    email_id: EmailStr = Field(
        Form(max_length=256, description="Email in RFC 5322 format")
    )
    location: str = Field(Form(description="Accepts only SRID 4326 (WGS84)"))


class UpdateFormForOP(BaseModel):
    id: int | None = Field(Form(default=None))
    address: str | None = Field(Form(max_length=512, default=None))
    contact_person: str | None = Field(Form(max_length=32, default=None))
    phone_number: PhoneNumber | None = Field(
        Form(max_length=32, default=None, description="Phone number in RFC3966 format")
    )
    email_id: EmailStr | None = Field(
        Form(max_length=256, default=None, description="Email in RFC 5322 format")
    )
    location: str | None = Field(
        Form(default=None, description="Accepts only SRID 4326 (WGS84)")
    )


class UpdateFormForEX(UpdateFormForOP):
    id: int = Field(Form())
    name: str | None = Field(Form(max_length=32, default=None))
    status: CompanyStatus | None = Field(
        Form(description=enumStr(CompanyStatus), default=None)
    )
    type: CompanyType | None = Field(
        Form(description=enumStr(CompanyType), default=None)
    )


class DeleteForm(BaseModel):
    id: int = Field(Form())


## Query Parameters
class OrderIn(IntEnum):
    ASC = 1
    DESC = 2


class OrderBy(IntEnum):
    id = 1
    location = 2
    updated_on = 3
    created_on = 4


class QueryParamsForVE(BaseModel):
    name: str | None = Field(Query(default=None))
    type: CompanyType | None = Field(
        Query(default=None, description=enumStr(CompanyType))
    )
    location: str | None = Field(
        Query(default=None, description="Accepts only SRID 4326 (WGS84)")
    )
    # id based
    id: int | None = Field(Query(default=None))
    id_ge: int | None = Field(Query(default=None))
    id_le: int | None = Field(Query(default=None))
    id_list: List[int] | None = Field(Query(default=None))
    # updated_on based
    updated_on_ge: datetime | None = Field(Query(default=None))
    updated_on_le: datetime | None = Field(Query(default=None))
    # created_on based
    created_on_ge: datetime | None = Field(Query(default=None))
    created_on_le: datetime | None = Field(Query(default=None))
    # Ordering
    order_by: OrderBy = Field(Query(default=OrderBy.id, description=enumStr(OrderBy)))
    order_in: OrderIn = Field(Query(default=OrderIn.DESC, description=enumStr(OrderIn)))
    # Pagination
    offset: int = Field(Query(default=0, ge=0))
    limit: int = Field(Query(default=20, gt=0, le=100))


class QueryParamsForEX(QueryParamsForVE):
    status: CompanyStatus | None = Field(
        Query(default=None, description=enumStr(CompanyStatus))
    )
    address: str | None = Field(Query(default=None))
    contact_person: str | None = Field(Query(default=None))
    phone_number: PhoneNumber | None = Field(
        Query(default=None, description="Phone number in RFC3966 format")
    )
    email_id: EmailStr | None = Field(
        Query(default=None, description="Email in RFC 5322 format")
    )


## Function
def updateCompany(company: Company, fParam: UpdateFormForEX | UpdateFormForOP):
    companyStatusTransition = {
        CompanyStatus.UNDER_VERIFICATION: [
            CompanyStatus.VERIFIED,
            CompanyStatus.SUSPENDED,
        ],
        CompanyStatus.VERIFIED: [CompanyStatus.SUSPENDED],
        CompanyStatus.SUSPENDED: [CompanyStatus.VERIFIED],
    }

    if isinstance(fParam, UpdateFormForEX):
        if fParam.name is not None and company.name != fParam.name:
            company.name = fParam.name
        if fParam.status is not None and company.status != fParam.status:
            validators.stateTransition(
                companyStatusTransition, company.status, fParam.status, Company.status
            )
            company.status = fParam.status
        if fParam.type is not None and company.type != fParam.type:
            company.type = fParam.type

    if fParam.address is not None and company.address != fParam.address:
        company.address = fParam.address
    if (
        fParam.contact_person is not None
        and company.contact_person != fParam.contact_person
    ):
        company.contact_person = fParam.contact_person
    if fParam.phone_number is not None and company.phone_number != fParam.phone_number:
        company.phone_number = fParam.phone_number
    if fParam.email_id is not None and company.email_id != fParam.email_id:
        company.email_id = fParam.email_id
    if fParam.location is not None:
        geometry = validators.WKTstring(fParam.location, Point)
        validators.SRID4326(geometry)
        fParam.location = wkt.dumps(geometry)

        currentLocation = (wkb.loads(bytes(company.location.data))).wkt
        if currentLocation != fParam.location:
            company.location = fParam.location


def searchCompany(
    session: Session, qParam: QueryParamsForEX | QueryParamsForVE
) -> List[Company]:
    query = session.query(Company)

    # Pre-processing
    if qParam.location is not None:
        geometry = validators.WKTstring(qParam.location, Point)
        validators.SRID4326(geometry)
        qParam.location = wkt.dumps(geometry)

    # Filters
    if qParam.name is not None:
        query = query.filter(Company.name.ilike(f"%{qParam.name}%"))
    if qParam.status is not None:
        query = query.filter(Company.status == qParam.status)
    if qParam.type is not None:
        query = query.filter(Company.type == qParam.type)
    if qParam.address is not None:
        query = query.filter(Company.address.ilike(f"%{qParam.address}%"))
    if qParam.contact_person is not None:
        query = query.filter(Company.contact_person.ilike(f"%{qParam.contact_person}%"))
    if qParam.phone_number is not None:
        query = query.filter(Company.phone_number.ilike(f"%{qParam.phone_number}%"))
    if qParam.email_id is not None:
        query = query.filter(Company.email_id.ilike(f"%{qParam.email_id}%"))
    # id based
    if qParam.id is not None:
        query = query.filter(Company.id == qParam.id)
    if qParam.id_ge is not None:
        query = query.filter(Company.id >= qParam.id_ge)
    if qParam.id_le is not None:
        query = query.filter(Company.id <= qParam.id_le)
    if qParam.id_list is not None:
        query = query.filter(Company.id.in_(qParam.id_list))
    # updated_on based
    if qParam.updated_on_ge is not None:
        query = query.filter(Company.updated_on >= qParam.updated_on_ge)
    if qParam.updated_on_le is not None:
        query = query.filter(Company.updated_on <= qParam.updated_on_le)
    # created_on based
    if qParam.created_on_ge is not None:
        query = query.filter(Company.created_on >= qParam.created_on_ge)
    if qParam.created_on_le is not None:
        query = query.filter(Company.created_on <= qParam.created_on_le)

    # Ordering
    if qParam.order_by == OrderBy.location and qParam.location:
        orderingAttribute = func.ST_Distance(
            Company.location.cast(Geography), func.ST_GeogFromText(qParam.location)
        )
    else:
        orderingAttribute = getattr(Company, OrderBy(qParam.order_by).name)
    if qParam.order_in == OrderIn.ASC:
        query = query.order_by(orderingAttribute.asc())
    else:
        query = query.order_by(orderingAttribute.desc())

    # Pagination
    query = query.offset(qParam.offset).limit(qParam.limit)
    companies = query.all()

    # Post-processing
    for company in companies:
        company.location = (wkb.loads(bytes(company.location.data))).wkt
    return companies


## API endpoints [Executive]
@route_executive.post(
    "/company",
    tags=["Company"],
    response_model=CompanySchema,
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
    Create a new company.  
    Requires executive permissions with `create_company` role.  
    Validates location format and ensures all required fields are provided.
    """,
)
async def create_company(
    fParam: CreateForm = Depends(),
    bearer=Depends(bearer_executive),
    request_info=Depends(getters.requestInfo),
):
    try:
        session = sessionMaker()
        token = validators.executiveToken(bearer.credentials, session)
        role = getters.executiveRole(token, session)
        validators.executivePermission(role, ExecutiveRole.create_company)

        if fParam.location is not None:
            geometry = validators.WKTstring(fParam.location, Point)
            validators.SRID4326(geometry)
            fParam.location = wkt.dumps(geometry)

        company = Company(
            name=fParam.name,
            status=fParam.status,
            type=fParam.type,
            address=fParam.address,
            contact_person=fParam.contact_person,
            phone_number=fParam.phone_number,
            email_id=fParam.email_id,
            location=fParam.location,
        )
        session.add(company)
        session.commit()
        logEvent(token, request_info, jsonable_encoder(company))
        return company
    except Exception as e:
        exceptions.handle(e)
    finally:
        session.close()


@route_executive.patch(
    "/company",
    tags=["Company"],
    response_model=CompanySchema,
    responses=makeExceptionResponses(
        [
            exceptions.InvalidToken,
            exceptions.NoPermission,
            exceptions.InvalidIdentifier,
            exceptions.InvalidWKTStringOrType,
            exceptions.InvalidSRID4326,
            exceptions.InvalidStateTransition,
        ]
    ),
    description="""
    Update an existing company record.  
    Requires executive permissions with `update_company` role.  
    Updates only the provided fields and validates the location if present.
    
    Allowed status transitions:
        UNDER_VERIFICATION → VERIFIED
        UNDER_VERIFICATION → SUSPENDED
        VERIFIED ↔ SUSPENDED
    """,
)
async def update_company(
    fParam: UpdateFormForEX = Depends(),
    bearer=Depends(bearer_executive),
    request_info=Depends(getters.requestInfo),
):
    try:
        session = sessionMaker()
        token = validators.executiveToken(bearer.credentials, session)
        role = getters.executiveRole(token, session)
        validators.executivePermission(role, ExecutiveRole.update_company)

        company = session.query(Company).filter(Company.id == fParam.id).first()
        if company is None:
            raise exceptions.InvalidIdentifier()

        updateCompany(company, fParam)
        haveUpdates = session.is_modified(company)
        if haveUpdates:
            session.commit()
            session.refresh(company)

        companyData = jsonable_encoder(company, exclude={"location"})
        companyData["location"] = (wkb.loads(bytes(company.location.data))).wkt
        if haveUpdates:
            logEvent(token, request_info, companyData)
        return companyData
    except Exception as e:
        exceptions.handle(e)
    finally:
        session.close()


@route_executive.delete(
    "/company",
    tags=["Company"],
    status_code=status.HTTP_204_NO_CONTENT,
    responses=makeExceptionResponses(
        [exceptions.InvalidToken, exceptions.NoPermission]
    ),
    description="""
    Delete an existing company by ID.  
    Requires executive permissions with `delete_company` role.  
    Deletes the company and logs the deletion event.
    """,
)
async def delete_company(
    fParam: DeleteForm = Depends(),
    bearer=Depends(bearer_executive),
    request_info=Depends(getters.requestInfo),
):
    try:
        session = sessionMaker()
        token = validators.executiveToken(bearer.credentials, session)
        role = getters.executiveRole(token, session)
        validators.executivePermission(role, ExecutiveRole.delete_company)

        company = session.query(Company).filter(Company.id == fParam.id).first()
        if company is not None:
            session.delete(company)
            session.commit()
            companyData = jsonable_encoder(company, exclude={"location"})
            companyData["location"] = (wkb.loads(bytes(company.location.data))).wkt
            logEvent(token, request_info, companyData)
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    except Exception as e:
        exceptions.handle(e)
    finally:
        session.close()


@route_executive.get(
    "/company",
    tags=["Company"],
    response_model=List[CompanySchema],
    responses=makeExceptionResponses(
        [
            exceptions.InvalidToken,
            exceptions.InvalidWKTStringOrType,
            exceptions.InvalidSRID4326,
        ]
    ),
    description="""
    Fetch a list of companies with optional filters like ID, name, type, location, etc.  
    Supports sorting and pagination.  
    Requires a valid executive token.
    """,
)
async def fetch_company(
    qParam: QueryParamsForEX = Depends(), bearer=Depends(bearer_executive)
):
    try:
        session = sessionMaker()
        validators.executiveToken(bearer.credentials, session)

        return searchCompany(session, qParam)
    except Exception as e:
        exceptions.handle(e)
    finally:
        session.close()


## API endpoints [Vendor]
@route_vendor.get(
    "/company",
    tags=["Company"],
    response_model=List[CompanySchemaForVE],
    responses=makeExceptionResponses(
        [
            exceptions.InvalidToken,
            exceptions.InvalidWKTStringOrType,
            exceptions.InvalidSRID4326,
        ]
    ),
    description="""
    Fetch a list of verified companies for vendor view.  
    Filters out sensitive fields like contact info.  
    Requires a valid vendor token.
    """,
)
async def fetch_company(
    qParam: QueryParamsForVE = Depends(), bearer=Depends(bearer_vendor)
):
    try:
        session = sessionMaker()
        validators.vendorToken(bearer.credentials, session)

        qParam = QueryParamsForEX(
            **qParam.model_dump(),
            status=CompanyStatus.VERIFIED,
            address=None,
            contact_person=None,
            phone_number=None,
            email_id=None,
        )
        return searchCompany(session, qParam)
    except Exception as e:
        exceptions.handle(e)
    finally:
        session.close()


## API endpoints [Operator]
@route_operator.patch(
    "/company",
    tags=["Company"],
    response_model=CompanySchema,
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
    Update the operator's own company profile.  
    Requires operator permissions with `update_company` role.  
    Only allows modifying the company associated with the operator.
    """,
)
async def update_company(
    fParam: UpdateFormForOP = Depends(),
    bearer=Depends(bearer_operator),
    request_info=Depends(getters.requestInfo),
):
    try:
        session = sessionMaker()
        token = validators.operatorToken(bearer.credentials, session)
        role = getters.operatorRole(token, session)
        validators.operatorPermission(role, OperatorRole.update_company)

        if fParam.id is None:
            fParam.id = token.company_id

        company = session.query(Company).filter(Company.id == fParam.id).first()
        if company is None or company.id != token.company_id:
            raise exceptions.InvalidIdentifier()

        updateCompany(company, fParam)
        haveUpdates = session.is_modified(company)
        if haveUpdates:
            session.commit()
            session.refresh(company)

        companyData = jsonable_encoder(company, exclude={"location"})
        companyData["location"] = (wkb.loads(bytes(company.location.data))).wkt
        if haveUpdates:
            logEvent(token, request_info, companyData)
        return companyData
    except Exception as e:
        exceptions.handle(e)
    finally:
        session.close()


@route_operator.get(
    "/company",
    tags=["Company"],
    response_model=List[CompanySchema],
    responses=makeExceptionResponses(
        [
            exceptions.InvalidToken,
        ]
    ),
    description="""
    Fetch the company information associated with the current operator.  
    Returns a list with a single item.  
    Requires a valid operator token.
    """,
)
async def fetch_company(bearer=Depends(bearer_operator)):
    try:
        session = sessionMaker()
        token = validators.operatorToken(bearer.credentials, session)

        company = session.query(Company).filter(Company.id == token.company_id).first()
        companyData = jsonable_encoder(company, exclude={"location"})
        companyData["location"] = (wkb.loads(bytes(company.location.data))).wkt
        return [companyData]
    except Exception as e:
        exceptions.handle(e)
    finally:
        session.close()
