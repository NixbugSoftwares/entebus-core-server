from datetime import datetime
from enum import IntEnum
from typing import List, Optional
from fastapi import APIRouter, Depends, Query, Response, status, Form
from sqlalchemy.orm.session import Session
from fastapi.encoders import jsonable_encoder
from pydantic import BaseModel, Field, EmailStr
from pydantic_extra_types.phone_numbers import PhoneNumber
from shapely.geometry import Point
from shapely import wkt, wkb
from sqlalchemy import func
from geoalchemy2 import Geography

from app.api.bearer import bearer_executive, bearer_vendor
from app.src.db import (
    Business,
    ExecutiveRole,
    VendorRole,
    Wallet,
    BusinessWallet,
    VendorToken,
    sessionMaker,
)
from app.src import exceptions, validators, getters
from app.src.enums import BusinessStatus, BusinessType
from app.src.loggers import logEvent
from app.src.functions import enumStr, makeExceptionResponses, updateIfChanged

route_executive = APIRouter()
route_vendor = APIRouter()
route_public = APIRouter()


## Output Schema
class BusinessSchemaForPU(BaseModel):
    id: int
    name: str
    type: int
    updated_on: Optional[datetime]
    created_on: datetime


class BusinessSchema(BusinessSchemaForPU):
    status: int
    address: str
    contact_person: str
    phone_number: str
    email_id: str
    location: str


## Input Forms
class CreateForm(BaseModel):
    name: str = Field(Form(max_length=32))
    status: BusinessStatus = Field(
        Form(
            description=enumStr(BusinessStatus),
            default=BusinessStatus.ACTIVE,
        )
    )
    type: BusinessType = Field(
        Form(description=enumStr(BusinessType), default=BusinessType.OTHER)
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


class UpdateFormForVE(BaseModel):
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


class UpdateFormForEX(UpdateFormForVE):
    id: int = Field(Form())
    name: str | None = Field(Form(max_length=32, default=None))
    status: BusinessStatus | None = Field(
        Form(description=enumStr(BusinessStatus), default=None)
    )
    type: BusinessType | None = Field(
        Form(description=enumStr(BusinessType), default=None)
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
    id: int | None = Field(Query(default=None))


class QueryParamsForPU(QueryParamsForVE):
    name: str | None = Field(Query(default=None))
    type: BusinessType | None = Field(
        Query(default=None, description=enumStr(BusinessType))
    )
    location: str | None = Field(
        Query(default=None, description="Accepts only SRID 4326 (WGS84)")
    )
    # id based
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


class QueryParamsForEX(QueryParamsForPU):
    status: BusinessStatus | None = Field(
        Query(default=None, description=enumStr(BusinessStatus))
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
def updateBusiness(
    session: Session,
    business: Business,
    fParam: UpdateFormForVE | UpdateFormForEX,
):
    if isinstance(fParam, UpdateFormForEX):
        updateIfChanged(business, fParam, [Business.type.key])
        if fParam.name is not None and business.name != fParam.name:
            wallet = (
                session.query(Wallet)
                .join(BusinessWallet, Wallet.id == BusinessWallet.wallet_id)
                .filter(BusinessWallet.business_id == fParam.id)
                .first()
            )
            walletName = fParam.name + " wallet"
            wallet.name = walletName
            business.name = fParam.name
        if fParam.status is not None and business.status != fParam.status:
            if fParam.status == BusinessStatus.SUSPENDED:
                session.query(VendorToken).filter(
                    VendorToken.business_id == fParam.id
                ).delete()
            business.status = fParam.status

    updateIfChanged(
        business,
        fParam,
        [
            Business.address.key,
            Business.contact_person.key,
            Business.phone_number.key,
            Business.email_id.key,
        ],
    )
    if fParam.location is not None:
        geometry = validators.WKTstring(fParam.location, Point)
        validators.SRID4326(geometry)
        fParam.location = wkt.dumps(geometry)

        currentLocation = (wkb.loads(bytes(business.location.data))).wkt
        if currentLocation != fParam.location:
            business.location = fParam.location


def searchBusiness(
    session: Session, qParam: QueryParamsForVE | QueryParamsForEX | QueryParamsForPU
) -> List[Business]:
    query = session.query(Business)

    # Pre-processing
    if qParam.location is not None:
        geometry = validators.WKTstring(qParam.location, Point)
        validators.SRID4326(geometry)
        qParam.location = wkt.dumps(geometry)

    # Filters
    if qParam.name is not None:
        query = query.filter(Business.name.ilike(f"%{qParam.name}%"))
    if qParam.status is not None:
        query = query.filter(Business.status == qParam.status)
    if qParam.type is not None:
        query = query.filter(Business.type == qParam.type)
    if qParam.address is not None:
        query = query.filter(Business.address.ilike(f"%{qParam.address}%"))
    if qParam.contact_person is not None:
        query = query.filter(
            Business.contact_person.ilike(f"%{qParam.contact_person}%")
        )
    if qParam.phone_number is not None:
        query = query.filter(Business.phone_number.ilike(f"%{qParam.phone_number}%"))
    if qParam.email_id is not None:
        query = query.filter(Business.email_id.ilike(f"%{qParam.email_id}%"))
    # id based
    if qParam.id is not None:
        query = query.filter(Business.id == qParam.id)
    if qParam.id_ge is not None:
        query = query.filter(Business.id >= qParam.id_ge)
    if qParam.id_le is not None:
        query = query.filter(Business.id <= qParam.id_le)
    if qParam.id_list is not None:
        query = query.filter(Business.id.in_(qParam.id_list))
    # updated_on based
    if qParam.updated_on_ge is not None:
        query = query.filter(Business.updated_on >= qParam.updated_on_ge)
    if qParam.updated_on_le is not None:
        query = query.filter(Business.updated_on <= qParam.updated_on_le)
    # created_on based
    if qParam.created_on_ge is not None:
        query = query.filter(Business.created_on >= qParam.created_on_ge)
    if qParam.created_on_le is not None:
        query = query.filter(Business.created_on <= qParam.created_on_le)

    # Ordering
    if qParam.order_by == OrderBy.location and qParam.location:
        orderingAttribute = func.ST_Distance(
            Business.location.cast(Geography), func.ST_GeogFromText(qParam.location)
        )
    else:
        orderingAttribute = getattr(Business, OrderBy(qParam.order_by).name)
    if qParam.order_in == OrderIn.ASC:
        query = query.order_by(orderingAttribute.asc())
    else:
        query = query.order_by(orderingAttribute.desc())

    # Pagination
    query = query.offset(qParam.offset).limit(qParam.limit)
    businesses = query.all()

    # Post-processing
    for business in businesses:
        business.location = (wkb.loads(bytes(business.location.data))).wkt
    return businesses


## API endpoints [Executive]
@route_executive.post(
    "/business",
    tags=["Business"],
    response_model=BusinessSchema,
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
    Create a new business.  
    Requires executive permissions with `create_business` role.  
    A wallet is automatically created with the business name when a business is created.     
    Validates location format and ensures all required fields are provided.
    """,
)
async def create_business(
    fParam: CreateForm = Depends(),
    bearer=Depends(bearer_executive),
    request_info=Depends(getters.requestInfo),
):
    try:
        session = sessionMaker()
        token = validators.executiveToken(bearer.credentials, session)
        role = getters.executiveRole(token, session)
        validators.executivePermission(role, ExecutiveRole.create_business)

        if fParam.location is not None:
            geometry = validators.WKTstring(fParam.location, Point)
            validators.SRID4326(geometry)
            fParam.location = wkt.dumps(geometry)

        business = Business(
            name=fParam.name,
            status=fParam.status,
            type=fParam.type,
            address=fParam.address,
            contact_person=fParam.contact_person,
            phone_number=fParam.phone_number,
            email_id=fParam.email_id,
            location=fParam.location,
        )
        session.add(business)

        # Create Wallet
        walletName = fParam.name + " wallet"
        wallet = Wallet(
            name=walletName,
            balance=0,
        )
        session.add(wallet)
        session.flush()

        # Link Business to Wallet
        businessWallet = BusinessWallet(
            wallet_id=wallet.id,
            business_id=business.id,
        )
        session.add(businessWallet)
        session.commit()
        session.refresh(business)

        businessData = jsonable_encoder(business, exclude={"location"})
        businessData["location"] = (wkb.loads(bytes(business.location.data))).wkt
        logEvent(token, request_info, businessData)
        return businessData
    except Exception as e:
        exceptions.handle(e)
    finally:
        session.close()


@route_executive.patch(
    "/business",
    tags=["Business"],
    response_model=BusinessSchema,
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
    Update an existing business record.  
    Requires executive permissions with `update_business` role.  
    If the status is set to SUSPENDED, all tokens associated with that business vendors are revoked.      
    Updates only the provided fields and validates the location if present.
    """,
)
async def update_business(
    fParam: UpdateFormForEX = Depends(),
    bearer=Depends(bearer_executive),
    request_info=Depends(getters.requestInfo),
):
    try:
        session = sessionMaker()
        token = validators.executiveToken(bearer.credentials, session)
        role = getters.executiveRole(token, session)
        validators.executivePermission(role, ExecutiveRole.update_business)

        business = session.query(Business).filter(Business.id == fParam.id).first()
        if business is None:
            raise exceptions.InvalidIdentifier()

        updateBusiness(session, business, fParam)
        haveUpdates = session.is_modified(business)
        if haveUpdates:
            session.commit()
            session.refresh(business)

        businessData = jsonable_encoder(business, exclude={"location"})
        businessData["location"] = (wkb.loads(bytes(business.location.data))).wkt
        if haveUpdates:
            logEvent(token, request_info, businessData)
        return businessData
    except Exception as e:
        exceptions.handle(e)
    finally:
        session.close()


@route_executive.delete(
    "/business",
    tags=["Business"],
    status_code=status.HTTP_204_NO_CONTENT,
    responses=makeExceptionResponses(
        [exceptions.InvalidToken, exceptions.NoPermission]
    ),
    description="""
    Delete an existing business by ID.  
    Requires executive permissions with `delete_business` role.  
    Deletes the business and logs the deletion event.
    """,
)
async def delete_business(
    fParam: DeleteForm = Depends(),
    bearer=Depends(bearer_executive),
    request_info=Depends(getters.requestInfo),
):
    try:
        session = sessionMaker()
        token = validators.executiveToken(bearer.credentials, session)
        role = getters.executiveRole(token, session)
        validators.executivePermission(role, ExecutiveRole.delete_business)

        business = session.query(Business).filter(Business.id == fParam.id).first()
        if business is not None:
            session.delete(business)
            session.commit()
            businessData = jsonable_encoder(business, exclude={"location"})
            businessData["location"] = (wkb.loads(bytes(business.location.data))).wkt
            logEvent(token, request_info, businessData)
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    except Exception as e:
        exceptions.handle(e)
    finally:
        session.close()


@route_executive.get(
    "/business",
    tags=["Business"],
    response_model=List[BusinessSchema],
    responses=makeExceptionResponses(
        [
            exceptions.InvalidToken,
            exceptions.InvalidWKTStringOrType,
            exceptions.InvalidSRID4326,
        ]
    ),
    description="""
    Fetch a list of businesses with optional filters like ID, name, type, location, etc.  
    Supports sorting and pagination.  
    Requires a valid executive token.
    """,
)
async def fetch_business(
    qParam: QueryParamsForEX = Depends(), bearer=Depends(bearer_executive)
):
    try:
        session = sessionMaker()
        validators.executiveToken(bearer.credentials, session)

        return searchBusiness(session, qParam)
    except Exception as e:
        exceptions.handle(e)
    finally:
        session.close()


## API endpoints [Vendor]
@route_vendor.patch(
    "/business",
    tags=["Business"],
    response_model=BusinessSchema,
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
    Update the vendors's own business profile.  
    Requires vendor permissions with `update_business` role.    
    Only allows modifying the business associated with the vendor.
    """,
)
async def update_business(
    fParam: UpdateFormForVE = Depends(),
    bearer=Depends(bearer_vendor),
    request_info=Depends(getters.requestInfo),
):
    try:
        session = sessionMaker()
        token = validators.vendorToken(bearer.credentials, session)
        role = getters.vendorRole(token, session)
        validators.vendorPermission(role, VendorRole.update_business)

        if fParam.id is None:
            fParam.id = token.business_id

        business = session.query(Business).filter(Business.id == fParam.id).first()
        if business is None or business.id != token.business_id:
            raise exceptions.InvalidIdentifier()

        updateBusiness(session, business, fParam)
        haveUpdates = session.is_modified(business)
        if haveUpdates:
            session.commit()
            session.refresh(business)

        businessData = jsonable_encoder(business, exclude={"location"})
        businessData["location"] = (wkb.loads(bytes(business.location.data))).wkt
        if haveUpdates:
            logEvent(token, request_info, businessData)
        return businessData
    except Exception as e:
        exceptions.handle(e)
    finally:
        session.close()


@route_vendor.get(
    "/business",
    tags=["Business"],
    response_model=List[BusinessSchema],
    responses=makeExceptionResponses(
        [
            exceptions.InvalidToken,
            exceptions.InvalidIdentifier,
        ]
    ),
    description="""
    Fetch the business information associated with the current vendor.  
    Returns vendors's own business if no ID provided.    
    If ID provided, must match vendors's business.  
    Requires a valid vendor token.
    """,
)
async def fetch_business(
    qParam: QueryParamsForVE = Depends(), bearer=Depends(bearer_vendor)
):
    try:
        session = sessionMaker()
        token = validators.vendorToken(bearer.credentials, session)

        if qParam.id is None:
            qParam.id = token.business_id
        if qParam.id != token.business_id:
            raise exceptions.InvalidIdentifier()
        business = session.query(Business).filter(Business.id == qParam.id).first()
        if business is not None:
            businessData = jsonable_encoder(business, exclude={"location"})
            businessData["location"] = (wkb.loads(bytes(business.location.data))).wkt
        return [businessData]
    except Exception as e:
        exceptions.handle(e)
    finally:
        session.close()


## API endpoints [Public]
@route_public.get(
    "/business",
    tags=["Business"],
    response_model=List[BusinessSchemaForPU],
    responses=makeExceptionResponses(
        [
            exceptions.InvalidWKTStringOrType,
            exceptions.InvalidSRID4326,
        ]
    ),
    description="""
    Fetch a list of businesses or a specific business by ID.
    If ID is not provided, all businesses are returned.
    Requires no authentication.
    """,
)
async def fetch_business(qParam: QueryParamsForPU = Depends()):
    try:
        session = sessionMaker()

        qParam = QueryParamsForEX(
            **qParam.model_dump(),
            status=BusinessStatus.ACTIVE,
            address=None,
            contact_person=None,
            phone_number=None,
            email_id=None,
        )
        return searchBusiness(session, qParam)
    except Exception as e:
        exceptions.handle(e)
    finally:
        session.close()
