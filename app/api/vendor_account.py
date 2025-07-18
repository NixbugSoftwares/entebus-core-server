from datetime import datetime
from enum import IntEnum
from typing import List, Optional
from fastapi import APIRouter, Depends, Query, Response, status, Form
from sqlalchemy.orm.session import Session
from fastapi.encoders import jsonable_encoder
from pydantic import BaseModel, Field, EmailStr
from pydantic_extra_types.phone_numbers import PhoneNumber

from app.api.bearer import bearer_executive, bearer_vendor
from app.src.constants import REGEX_PASSWORD, REGEX_USERNAME
from app.src.db import ExecutiveRole, Vendor, VendorRole, VendorToken, sessionMaker
from app.src import argon2, exceptions, validators, getters
from app.src.enums import AccountStatus, GenderType
from app.src.loggers import logEvent
from app.src.functions import enumStr, makeExceptionResponses, updateIfChanged
from app.src.functions import promoteToParent

route_vendor = APIRouter()
route_executive = APIRouter()


## Output Schema
class VendorSchema(BaseModel):
    id: int
    business_id: int
    username: str
    gender: int
    full_name: Optional[str]
    status: int
    phone_number: Optional[str]
    email_id: Optional[str]
    updated_on: Optional[datetime]
    created_on: datetime


## Input Forms
class CreateFormForVE(BaseModel):
    username: str = Field(Form(pattern=REGEX_USERNAME, min_length=4, max_length=32))
    password: str = Field(Form(pattern=REGEX_PASSWORD, min_length=8, max_length=32))
    gender: GenderType = Field(
        Form(description=enumStr(GenderType), default=GenderType.OTHER)
    )
    full_name: str | None = Field(Form(max_length=32, default=None))
    phone_number: PhoneNumber | None = Field(
        Form(max_length=32, default=None, description="Phone number in RFC3966 format")
    )
    email_id: EmailStr | None = Field(
        Form(max_length=256, default=None, description="Email in RFC 5322 format")
    )


class CreateFormForEX(CreateFormForVE):
    business_id: int = Field(Form())


class UpdateFormForVE(BaseModel):
    id: int | None = Field(Form(default=None))
    password: str | None = Field(
        Form(pattern=REGEX_PASSWORD, min_length=8, max_length=32, default=None)
    )
    gender: GenderType | None = Field(
        Form(description=enumStr(GenderType), default=None)
    )
    full_name: str | None = Field(Form(max_length=32, default=None))
    status: AccountStatus | None = Field(
        Form(description=enumStr(AccountStatus), default=None)
    )
    phone_number: PhoneNumber | None = Field(
        Form(max_length=32, default=None, description="Phone number in RFC3966 format")
    )
    email_id: EmailStr | None = Field(
        Form(max_length=256, default=None, description="Email in RFC 5322 format")
    )


class UpdateFormForEX(UpdateFormForVE):
    id: int = Field(Form())


class DeleteForm(BaseModel):
    id: int = Field(Form())


## Query Parameters
class OrderIn(IntEnum):
    ASC = 1
    DESC = 2


class OrderBy(IntEnum):
    id = 1
    updated_on = 2
    created_on = 3


class QueryParamForVE(BaseModel):
    username: str | None = Field(Query(default=None))
    gender: GenderType | None = Field(
        Query(default=None, description=enumStr(GenderType))
    )
    full_name: str | None = Field(Query(default=None))
    status: AccountStatus | None = Field(
        Query(default=None, description=enumStr(AccountStatus))
    )
    phone_number: str | None = Field(Query(default=None))
    email_id: str | None = Field(Query(default=None))
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


class QueryParamsForEX(QueryParamForVE):
    business_id: int | None = Field(Query(default=None))


## Function
def updateVendor(
    session: Session, vendor: Vendor, fParam: UpdateFormForVE | UpdateFormForEX
):
    updateIfChanged(
        vendor,
        fParam,
        [
            Vendor.gender.key,
            Vendor.full_name.key,
            Vendor.phone_number.key,
            Vendor.email_id.key,
        ],
    )
    if fParam.password is not None:
        vendor.password = argon2.makePassword(fParam.password)
    if fParam.status is not None and vendor.status != fParam.status:
        if fParam.status == AccountStatus.SUSPENDED:
            session.query(VendorToken).filter(
                VendorToken.vendor_id == fParam.id
            ).delete()
        vendor.status = fParam.status


def searchVendor(
    session: Session, qParam: QueryParamForVE | QueryParamsForEX
) -> List[Vendor]:
    query = session.query(Vendor)

    # Filters
    if qParam.username is not None:
        query = query.filter(Vendor.username.ilike(f"%{qParam.username}%"))
    if qParam.business_id is not None:
        query = query.filter(Vendor.business_id == qParam.business_id)
    if qParam.gender is not None:
        query = query.filter(Vendor.gender == qParam.gender)
    if qParam.full_name is not None:
        query = query.filter(Vendor.full_name.ilike(f"%{qParam.full_name}%"))
    if qParam.phone_number is not None:
        query = query.filter(Vendor.phone_number.ilike(f"%{qParam.phone_number}%"))
    if qParam.email_id is not None:
        query = query.filter(Vendor.email_id.ilike(f"%{qParam.email_id}%"))
    if qParam.status is not None:
        query = query.filter(Vendor.status == qParam.status)
    # id based
    if qParam.id is not None:
        query = query.filter(Vendor.id == qParam.id)
    if qParam.id_ge is not None:
        query = query.filter(Vendor.id >= qParam.id_ge)
    if qParam.id_le is not None:
        query = query.filter(Vendor.id <= qParam.id_le)
    if qParam.id_list is not None:
        query = query.filter(Vendor.id.in_(qParam.id_list))
    # updated_on based
    if qParam.updated_on_ge is not None:
        query = query.filter(Vendor.updated_on >= qParam.updated_on_ge)
    if qParam.updated_on_le is not None:
        query = query.filter(Vendor.updated_on <= qParam.updated_on_le)
    # created_on based
    if qParam.created_on_ge is not None:
        query = query.filter(Vendor.created_on >= qParam.created_on_ge)
    if qParam.created_on_le is not None:
        query = query.filter(Vendor.created_on <= qParam.created_on_le)

    # Ordering
    orderingAttribute = getattr(Vendor, OrderBy(qParam.order_by).name)
    if qParam.order_in == OrderIn.ASC:
        query = query.order_by(orderingAttribute.asc())
    else:
        query = query.order_by(orderingAttribute.desc())

    # Pagination
    query = query.offset(qParam.offset).limit(qParam.limit)
    return query.all()


## API endpoints [Executive]
@route_executive.post(
    "/business/account",
    tags=["Vendor Account"],
    response_model=VendorSchema,
    status_code=status.HTTP_201_CREATED,
    responses=makeExceptionResponses(
        [exceptions.InvalidToken, exceptions.NoPermission]
    ),
    description="""
    Creates a new vendor account with an active status.       
    Only executive with `create_vendor` permission can create vendor.       
    Logs the vendor account creation activity with the associated token.     
    Follow patterns for smooth creation of username and password.       
    The password is hashed using Argon2 before storing.
    """,
)
async def create_vendor(
    fParam: CreateFormForEX = Depends(),
    bearer=Depends(bearer_executive),
    request_info=Depends(getters.requestInfo),
):
    try:
        session = sessionMaker()
        token = validators.executiveToken(bearer.credentials, session)
        role = getters.executiveRole(token, session)
        validators.executivePermission(role, ExecutiveRole.create_vendor)

        fParam.password = argon2.makePassword(fParam.password)
        vendor = Vendor(
            business_id=fParam.business_id,
            username=fParam.username,
            password=fParam.password,
            gender=fParam.gender,
            full_name=fParam.full_name,
            phone_number=fParam.phone_number,
            email_id=fParam.email_id,
        )
        session.add(vendor)
        session.commit()
        session.refresh(vendor)

        vendorData = jsonable_encoder(vendor, exclude={"password"})
        logEvent(token, request_info, vendorData)
        return vendorData
    except Exception as e:
        exceptions.handle(e)
    finally:
        session.close()


@route_executive.patch(
    "/business/account",
    tags=["Vendor Account"],
    response_model=VendorSchema,
    responses=makeExceptionResponses(
        [exceptions.InvalidToken, exceptions.NoPermission, exceptions.InvalidIdentifier]
    ),
    description="""
    Updates an existing vendor account.       
    Executive with `update_vendor` permission can update vendors account.     
    Follow patterns for smooth creation of password.        
    The password is hashed using Argon2 before storing.         
    If the status is set to`SUSPENDED, all tokens associated with that vendor are revoked.      
    Logs the vendor account update activity with the associated token.
    """,
)
async def update_vendor(
    fParam: UpdateFormForEX = Depends(),
    bearer=Depends(bearer_executive),
    request_info=Depends(getters.requestInfo),
):
    try:
        session = sessionMaker()
        token = validators.executiveToken(bearer.credentials, session)
        role = getters.executiveRole(token, session)
        validators.executivePermission(role, ExecutiveRole.update_vendor)

        vendor = session.query(Vendor).filter(Vendor.id == fParam.id).first()
        if vendor is None:
            raise exceptions.InvalidIdentifier()

        updateVendor(session, vendor, fParam)
        haveUpdates = session.is_modified(vendor)
        if haveUpdates:
            session.commit()
            session.refresh(vendor)

        vendorData = jsonable_encoder(vendor, exclude={"password"})
        if haveUpdates:
            logEvent(token, request_info, vendorData)
        return vendorData
    except Exception as e:
        exceptions.handle(e)
    finally:
        session.close()


@route_executive.delete(
    "/business/account",
    tags=["Vendor Account"],
    status_code=status.HTTP_204_NO_CONTENT,
    responses=makeExceptionResponses(
        [exceptions.InvalidToken, exceptions.NoPermission]
    ),
    description="""
    Delete an existing vendor by ID.  
    Requires executive permissions with `delete_vendor` role.  
    Deletes the vendor and logs the deletion event.
    """,
)
async def delete_vendor(
    fParam: DeleteForm = Depends(),
    bearer=Depends(bearer_executive),
    request_info=Depends(getters.requestInfo),
):
    try:
        session = sessionMaker()
        token = validators.executiveToken(bearer.credentials, session)
        role = getters.executiveRole(token, session)
        validators.executivePermission(role, VendorRole.delete_vendor)

        vendor = session.query(Vendor).filter(Vendor.id == fParam.id).first()
        if vendor is not None:
            session.delete(vendor)
            session.commit()
            logEvent(
                token, request_info, jsonable_encoder(vendor, exclude={"password"})
            )
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    except Exception as e:
        exceptions.handle(e)
    finally:
        session.close()


@route_executive.get(
    "/business/account",
    tags=["Vendor Account"],
    response_model=List[VendorSchema],
    responses=makeExceptionResponses([exceptions.InvalidToken]),
    description="""
    Fetch vendor accounts with filtering, sorting, and pagination.    
    Filter by business_id, username, gender, designation, contact details, status, and creation/update timestamps.   
    Filter by ID ranges or lists.    
    Sort by ID, creation date, or update date in ascending or descending order.     
    Paginate using offset and limit.    
    Returns a list of vendor accounts matching the criteria.      
    Requires a valid executive token.
    """,
)
async def fetch_vendor(
    qParam: QueryParamsForEX = Depends(), bearer=Depends(bearer_executive)
):
    try:
        session = sessionMaker()
        validators.executiveToken(bearer.credentials, session)

        return searchVendor(session, qParam)
    except Exception as e:
        exceptions.handle(e)
    finally:
        session.close()


## API endpoints [Vendor]
@route_vendor.post(
    "/business/account",
    tags=["Account"],
    response_model=VendorSchema,
    status_code=status.HTTP_201_CREATED,
    responses=makeExceptionResponses(
        [exceptions.InvalidToken, exceptions.NoPermission]
    ),
    description="""
    Creates a new vendor account with an active status, associated with the current vendor business.     
    Only vendor with `create_vendor` permission can create vendor.        
    Logs the vendor account creation activity with the associated token.      
    Follow patterns for smooth creation of username and password.       
    The password is hashed using Argon2 before storing.         
    Duplicate usernames are not allowed.
    """,
)
async def create_vendor(
    fParam: CreateFormForVE = Depends(),
    bearer=Depends(bearer_vendor),
    request_info=Depends(getters.requestInfo),
):
    try:
        session = sessionMaker()
        token = validators.vendorToken(bearer.credentials, session)
        role = getters.vendorRole(token, session)
        validators.vendorPermission(role, VendorRole.create_vendor)

        fParam.password = argon2.makePassword(fParam.password)
        vendor = Vendor(
            business_id=token.business_id,
            username=fParam.username,
            password=fParam.password,
            gender=fParam.gender,
            full_name=fParam.full_name,
            phone_number=fParam.phone_number,
            email_id=fParam.email_id,
        )
        session.add(vendor)
        session.commit()
        session.refresh(vendor)

        vendorData = jsonable_encoder(vendor, exclude={"password"})
        logEvent(token, request_info, vendorData)
        return vendorData
    except Exception as e:
        exceptions.handle(e)
    finally:
        session.close()


@route_vendor.patch(
    "/business/account",
    tags=["Account"],
    response_model=VendorSchema,
    responses=makeExceptionResponses(
        [exceptions.InvalidToken, exceptions.NoPermission, exceptions.InvalidIdentifier]
    ),
    description="""
    Updates an existing vendor account associated with the current vendor business.      
    Vendor can update their own account but cannot update their own status.       
    Vendor with `update_vendor` permission can update other vendors.      
    Follow patterns for smooth creation of username and password.       
    Password changes are securely hashed.       
    If the status is set to SUSPENDED, all tokens associated with that vendor are revoked.      
    Logs the vendor account update activity with the associated token.
    """,
)
async def update_vendor(
    fParam: UpdateFormForVE = Depends(),
    bearer=Depends(bearer_vendor),
    request_info=Depends(getters.requestInfo),
):
    try:
        session = sessionMaker()
        token = validators.vendorToken(bearer.credentials, session)
        role = getters.vendorRole(token, session)

        if fParam.id is None:
            fParam.id = token.vendor_id
        isSelfUpdate = fParam.id == token.vendor_id
        hasUpdatePermission = bool(role and role.update_vendor)
        if not isSelfUpdate and not hasUpdatePermission:
            raise exceptions.NoPermission()
        if fParam.status == AccountStatus.SUSPENDED and isSelfUpdate:
            raise exceptions.NoPermission()

        vendor = (
            session.query(Vendor)
            .filter(Vendor.id == fParam.id)
            .filter(Vendor.business_id == token.business_id)
            .first()
        )
        if vendor is None:
            raise exceptions.InvalidIdentifier()

        updateVendor(session, vendor, fParam)
        haveUpdates = session.is_modified(vendor)
        if haveUpdates:
            session.commit()
            session.refresh(vendor)

        vendorData = jsonable_encoder(vendor, exclude={"password"})
        if haveUpdates:
            logEvent(token, request_info, vendorData)
        return vendorData
    except Exception as e:
        exceptions.handle(e)
    finally:
        session.close()


@route_vendor.delete(
    "/business/account",
    tags=["Account"],
    status_code=status.HTTP_204_NO_CONTENT,
    responses=makeExceptionResponses(
        [exceptions.InvalidToken, exceptions.NoPermission]
    ),
    description="""
    Delete an vendor account associated with the current vendor business.        
    Only users with the `delete_vendor` permission can delete vendor accounts.        
    Self-deletion is not allowed for safety reasons.    
    If the specified vendor exists, it will be deleted permanently.    
    The deleted account details are logged for audit purposes.
    """,
)
async def delete_vendor(
    fParam: DeleteForm = Depends(),
    bearer=Depends(bearer_vendor),
    request_info=Depends(getters.requestInfo),
):
    try:
        session = sessionMaker()
        token = validators.vendorToken(bearer.credentials, session)
        role = getters.vendorRole(token, session)
        validators.vendorPermission(role, VendorRole.delete_vendor)

        # Prevent self deletion
        if fParam.id == token.business_id:
            raise exceptions.NoPermission()

        vendor = (
            session.query(Vendor)
            .filter(Vendor.id == fParam.id)
            .filter(Vendor.business_id == token.business_id)
            .first()
        )
        if vendor is not None:
            session.delete(vendor)
            session.commit()
            logEvent(
                token, request_info, jsonable_encoder(vendor, exclude={"password"})
            )
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    except Exception as e:
        exceptions.handle(e)
    finally:
        session.close()


@route_vendor.get(
    "/business/account",
    tags=["Account"],
    response_model=List[VendorSchema],
    responses=makeExceptionResponses([exceptions.InvalidToken]),
    description="""
    Fetch the vendor information associated with the current vendor business.     
    Filter by username, gender, designation, contact details, status, and creation/update timestamps.      
    Filter by ID ranges or lists.       
    Sort by ID, creation date, or update date in ascending or descending order.     
    Paginate using offset and limit.        
    Returns a list of vendor accounts matching the criteria.      
    Requires a valid vendor token.
    """,
)
async def fetch_vendor(
    qParam: QueryParamForVE = Depends(), bearer=Depends(bearer_vendor)
):
    try:
        session = sessionMaker()
        token = validators.vendorToken(bearer.credentials, session)

        qParam = promoteToParent(
            qParam, QueryParamsForEX, business_id=token.business_id
        )
        return searchVendor(session, qParam)
    except Exception as e:
        exceptions.handle(e)
    finally:
        session.close()
