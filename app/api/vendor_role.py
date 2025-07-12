from datetime import datetime
from enum import IntEnum
from typing import List, Optional
from fastapi import APIRouter, Depends, Query, Response, status, Form
from fastapi.encoders import jsonable_encoder
from pydantic import BaseModel, Field
from sqlalchemy.orm.session import Session

from app.api.bearer import bearer_executive, bearer_vendor
from app.src.db import VendorRole, ExecutiveRole, sessionMaker
from app.src import exceptions, validators, getters
from app.src.loggers import logEvent
from app.src.functions import enumStr, makeExceptionResponses

route_executive = APIRouter()
route_vendor = APIRouter()


## Output Schema
class VendorRoleSchema(BaseModel):
    id: int
    name: str
    business_id: int
    manage_token: bool
    update_business: bool
    create_vendor: bool
    update_vendor: bool
    delete_vendor: bool
    create_role: bool
    update_role: bool
    delete_role: bool
    updated_on: Optional[datetime]
    created_on: datetime


class CreateFormForVE(BaseModel):
    name: str = Field(Form(max_length=32))
    manage_token: bool = Field(Form(default=False))
    update_business: bool = Field(Form(default=False))
    create_vendor: bool = Field(Form(default=False))
    update_vendor: bool = Field(Form(default=False))
    delete_vendor: bool = Field(Form(default=False))
    create_role: bool = Field(Form(default=False))
    update_role: bool = Field(Form(default=False))
    delete_role: bool = Field(Form(default=False))


class CreateFormForEX(CreateFormForVE):
    business_id: int = Field(Form())


class UpdateForm(BaseModel):
    id: int = Field(Form())
    name: str | None = Field(Form(max_length=32, default=None))
    manage_token: bool | None = Field(Form(default=None))
    update_business: bool | None = Field(Form(default=None))
    create_vendor: bool | None = Field(Form(default=None))
    update_vendor: bool | None = Field(Form(default=None))
    delete_vendor: bool | None = Field(Form(default=None))
    create_role: bool | None = Field(Form(default=None))
    update_role: bool | None = Field(Form(default=None))
    delete_role: bool | None = Field(Form(default=None))


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


class QueryParamsForVE(BaseModel):
    name: str | None = Field(Query(default=None))
    # id based
    id: int | None = Field(Query(default=None))
    id_ge: int | None = Field(Query(default=None))
    id_le: int | None = Field(Query(default=None))
    id_list: List[int] | None = Field(Query(default=None))
    # Token management permissions based
    manage_token: bool | None = Field(Query(default=None))
    # Business management permissions based
    update_business: bool | None = Field(Query(default=None))
    # Vendor management permissions based
    create_vendor: bool | None = Field(Query(default=None))
    update_vendor: bool | None = Field(Query(default=None))
    delete_vendor: bool | None = Field(Query(default=None))
    # Executive role management permissions based
    create_role: bool | None = Field(Query(default=None))
    update_role: bool | None = Field(Query(default=None))
    delete_role: bool | None = Field(Query(default=None))
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
    business_id: int | None = Field(Query(default=None))


## Functions
def updateRole(role: VendorRole, fParam: UpdateForm):
    if fParam.name is not None and role.name != fParam.name:
        role.name = fParam.name
    if fParam.manage_token is not None and role.manage_token != fParam.manage_token:
        role.manage_token = fParam.manage_token
    if (
        fParam.update_business is not None
        and role.update_business != fParam.update_business
    ):
        role.update_business = fParam.update_business
    if fParam.create_vendor is not None and role.create_vendor != fParam.create_vendor:
        role.create_vendor = fParam.create_vendor
    if fParam.update_vendor is not None and role.update_vendor != fParam.update_vendor:
        role.update_vendor = fParam.update_vendor
    if fParam.delete_vendor is not None and role.delete_vendor != fParam.delete_vendor:
        role.delete_vendor = fParam.delete_vendor
    if fParam.create_role is not None and role.create_role != fParam.create_role:
        role.create_role = fParam.create_role
    if fParam.update_role is not None and role.update_role != fParam.update_role:
        role.update_role = fParam.update_role
    if fParam.delete_role is not None and role.delete_role != fParam.delete_role:
        role.delete_role = fParam.delete_role


def searchRole(
    session: Session, qParam: QueryParamsForVE | QueryParamsForEX
) -> List[VendorRole]:
    query = session.query(VendorRole)

    if qParam.name is not None:
        query = query.filter(VendorRole.name.like(f"%{qParam.name}%"))
    if qParam.business_id is not None:
        query = query.filter(VendorRole.business_id == qParam.business_id)
    # id based
    if qParam.id is not None:
        query = query.filter(VendorRole.id == qParam.id)
    if qParam.id_ge is not None:
        query = query.filter(VendorRole.id >= qParam.id_ge)
    if qParam.id_le is not None:
        query = query.filter(VendorRole.id <= qParam.id_le)
    if qParam.id_list is not None:
        query = query.filter(VendorRole.id.in_(qParam.id_list))
    # Token management permissions
    if qParam.manage_token is not None:
        query = query.filter(VendorRole.manage_token == qParam.manage_token)
    # Business permissions
    if qParam.update_business is not None:
        query = query.filter(VendorRole.update_business == qParam.update_business)
    # Vendor permissions
    if qParam.create_vendor is not None:
        query = query.filter(VendorRole.create_vendor == qParam.create_vendor)
    if qParam.update_vendor is not None:
        query = query.filter(VendorRole.update_vendor == qParam.update_vendor)
    if qParam.delete_vendor is not None:
        query = query.filter(VendorRole.delete_vendor == qParam.delete_vendor)
    # Executive role permissions
    if qParam.create_role is not None:
        query = query.filter(VendorRole.create_role == qParam.create_role)
    if qParam.update_role is not None:
        query = query.filter(VendorRole.update_role == qParam.update_role)
    if qParam.delete_role is not None:
        query = query.filter(VendorRole.delete_role == qParam.delete_role)
    # updated_on based
    if qParam.updated_on_ge is not None:
        query = query.filter(VendorRole.updated_on >= qParam.updated_on_ge)
    if qParam.updated_on_le is not None:
        query = query.filter(VendorRole.updated_on <= qParam.updated_on_le)
    # created_on based
    if qParam.created_on_ge is not None:
        query = query.filter(VendorRole.created_on >= qParam.created_on_ge)
    if qParam.created_on_le is not None:
        query = query.filter(VendorRole.created_on <= qParam.created_on_le)

    # Ordering
    orderingAttribute = getattr(VendorRole, OrderBy(qParam.order_by).name)
    if qParam.order_in == OrderIn.ASC:
        query = query.order_by(orderingAttribute.asc())
    else:
        query = query.order_by(orderingAttribute.desc())

    # Pagination
    query = query.offset(qParam.offset).limit(qParam.limit)
    return query.all()


## API endpoints [Executive]
@route_executive.post(
    "/business/role",
    tags=["Vendor Role"],
    response_model=VendorRoleSchema,
    status_code=status.HTTP_201_CREATED,
    responses=makeExceptionResponses(
        [exceptions.InvalidToken, exceptions.NoPermission]
    ),
    description="""
    Create a new vendor role.     
    Only authorized users with `create_ve_role` permission can create a new role.      
    Role name must be unique across the business.        
    Log the role creation activity with the associated token.
    """,
)
async def create_role(
    fParam: CreateFormForEX = Depends(),
    bearer=Depends(bearer_executive),
    request_info=Depends(getters.requestInfo),
):
    try:
        session = sessionMaker()
        token = validators.executiveToken(bearer.credentials, session)
        role = getters.executiveRole(token, session)
        validators.executivePermission(role, ExecutiveRole.create_ve_role)

        role = VendorRole(
            name=fParam.name,
            business_id=fParam.business_id,
            manage_token=fParam.manage_token,
            update_business=fParam.update_business,
            create_vendor=fParam.create_vendor,
            update_vendor=fParam.update_vendor,
            delete_vendor=fParam.delete_vendor,
            create_role=fParam.create_role,
            update_role=fParam.update_role,
            delete_role=fParam.delete_role,
        )
        session.add(role)
        session.commit()
        logEvent(token, request_info, jsonable_encoder(role))
        return role
    except Exception as e:
        exceptions.handle(e)
    finally:
        session.close()


@route_executive.patch(
    "/business/role",
    tags=["Vendor Role"],
    response_model=VendorRoleSchema,
    responses=makeExceptionResponses(
        [
            exceptions.InvalidToken,
            exceptions.NoPermission,
            exceptions.InvalidIdentifier,
        ]
    ),
    description="""
    Updates an existing vendor role.       
    Only executives with `update_ve_role` permission can perform this operation.    
    Support partial updates such as modifying the role name.       
    Changes are saved only if the role data has been modified.        
    Logs the role updating activity with the associated token.
    """,
)
async def update_role(
    fParam: UpdateForm = Depends(),
    bearer=Depends(bearer_executive),
    request_info=Depends(getters.requestInfo),
):
    try:
        session = sessionMaker()
        token = validators.executiveToken(bearer.credentials, session)
        role = getters.executiveRole(token, session)
        validators.executivePermission(role, ExecutiveRole.update_ve_role)

        role = session.query(VendorRole).filter(VendorRole.id == fParam.id).first()
        if role is None:
            raise exceptions.InvalidIdentifier()

        updateRole(role, fParam)
        haveUpdates = session.is_modified(role)
        if haveUpdates:
            session.commit()
            session.refresh(role)

        roleData = jsonable_encoder(role)
        if haveUpdates:
            logEvent(token, request_info, roleData)
        return roleData
    except Exception as e:
        exceptions.handle(e)
    finally:
        session.close()


@route_executive.delete(
    "/business/role",
    tags=["Vendor Role"],
    status_code=status.HTTP_204_NO_CONTENT,
    responses=makeExceptionResponses(
        [exceptions.InvalidToken, exceptions.NoPermission]
    ),
    description="""
    Deletes an existing vendor role.       
    Only executives with `delete_ve_role` permission can perform this operation.    
    Validates the role ID before deletion.       
    If the role exists, it is permanently removed from the system.       
    Logs the deletion activity using the executive's token and request metadata.
    """,
)
async def delete_role(
    fParam: DeleteForm = Depends(),
    bearer=Depends(bearer_executive),
    request_info=Depends(getters.requestInfo),
):
    try:
        session = sessionMaker()
        token = validators.executiveToken(bearer.credentials, session)
        role = getters.executiveRole(token, session)
        validators.executivePermission(role, ExecutiveRole.delete_ve_role)

        role = session.query(VendorRole).filter(VendorRole.id == fParam.id).first()
        if role is not None:
            session.delete(role)
            session.commit()
            logEvent(token, request_info, jsonable_encoder(role))
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    except Exception as e:
        exceptions.handle(e)
    finally:
        session.close()


@route_executive.get(
    "/business/role",
    tags=["Vendor Role"],
    response_model=List[VendorRoleSchema],
    responses=makeExceptionResponses([exceptions.InvalidToken]),
    description="""
    Fetches a list of all vendor role across business.       
    Supports filtering by ID, name, permissions and metadata.   
    Supports filtering, sorting, and pagination.     
    Requires a valid executive token.
    """,
)
async def fetch_role(
    qParam: QueryParamsForEX = Depends(), bearer=Depends(bearer_executive)
):
    try:
        session = sessionMaker()
        validators.executiveToken(bearer.credentials, session)

        return searchRole(session, qParam)
    except Exception as e:
        exceptions.handle(e)
    finally:
        session.close()


## API endpoints [Vendor]
@route_vendor.post(
    "/business/role",
    tags=["Role"],
    response_model=VendorRoleSchema,
    status_code=status.HTTP_201_CREATED,
    responses=makeExceptionResponses(
        [exceptions.InvalidToken, exceptions.NoPermission]
    ),
    description="""
    Creates a new vendor role, associated with the current vendor business.     
    Only vendors with `create_role` permission can create role.        
    Logs the vendor role creation activity with the associated token.             
    Duplicate names are not allowed.
    """,
)
async def create_role(
    fParam: CreateFormForVE = Depends(),
    bearer=Depends(bearer_vendor),
    request_info=Depends(getters.requestInfo),
):
    try:
        session = sessionMaker()
        token = validators.vendorToken(bearer.credentials, session)
        role = getters.vendorRole(token, session)
        validators.vendorPermission(role, VendorRole.create_role)

        role = VendorRole(
            name=fParam.name,
            business_id=token.business_id,
            manage_token=fParam.manage_token,
            update_business=fParam.update_business,
            create_vendor=fParam.create_vendor,
            update_vendor=fParam.update_vendor,
            delete_vendor=fParam.delete_vendor,
            create_role=fParam.create_role,
            update_role=fParam.update_role,
            delete_role=fParam.delete_role,
        )
        session.add(role)
        session.commit()
        logEvent(token, request_info, jsonable_encoder(role))
        return role
    except Exception as e:
        exceptions.handle(e)
    finally:
        session.close()


@route_vendor.patch(
    "/business/role",
    tags=["Role"],
    response_model=VendorRoleSchema,
    responses=makeExceptionResponses(
        [
            exceptions.InvalidToken,
            exceptions.NoPermission,
            exceptions.InvalidIdentifier,
        ]
    ),
    description="""
    Updates an existing vendor role associated with the current vendor business.             
    Vendor with `update_role` permission can update other vendors role.     
    Support partial updates such as modifying the role name.    
    Changes are saved only if the role data has been modified.         
    Logs the vendor role update activity with the associated token.
    """,
)
async def update_role(
    fParam: UpdateForm = Depends(),
    bearer=Depends(bearer_vendor),
    request_info=Depends(getters.requestInfo),
):
    try:
        session = sessionMaker()
        token = validators.vendorToken(bearer.credentials, session)
        role = getters.vendorRole(token, session)
        validators.vendorPermission(role, VendorRole.update_role)

        role = (
            session.query(VendorRole)
            .filter(VendorRole.id == fParam.id)
            .filter(VendorRole.business_id == token.business_id)
            .first()
        )
        if role is None:
            raise exceptions.InvalidIdentifier()

        updateRole(role, fParam)
        haveUpdates = session.is_modified(role)
        if haveUpdates:
            session.commit()
            session.refresh(role)

        roleData = jsonable_encoder(role)
        if haveUpdates:
            logEvent(token, request_info, roleData)
        return roleData
    except Exception as e:
        exceptions.handle(e)
    finally:
        session.close()


@route_vendor.delete(
    "/business/role",
    tags=["Role"],
    status_code=status.HTTP_204_NO_CONTENT,
    responses=makeExceptionResponses(
        [exceptions.InvalidToken, exceptions.NoPermission]
    ),
    description="""
    Deletes an existing vendor role.       
    Only users with the `delete_role` permission can delete vendor accounts.       
    Validates the role ID before deletion.       
    If the role exists, it is permanently removed from the system.       
    Logs the deletion activity using the vendor's token and request metadata. 
    """,
)
async def delete_role(
    fParam: DeleteForm = Depends(),
    bearer=Depends(bearer_vendor),
    request_info=Depends(getters.requestInfo),
):
    try:
        session = sessionMaker()
        token = validators.vendorToken(bearer.credentials, session)
        role = getters.vendorRole(token, session)
        validators.vendorPermission(role, VendorRole.delete_role)

        role = (
            session.query(VendorRole)
            .filter(VendorRole.id == fParam.id)
            .filter(VendorRole.business_id == token.business_id)
            .first()
        )
        if role is not None:
            session.delete(role)
            session.commit()
            logEvent(token, request_info, jsonable_encoder(role))
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    except Exception as e:
        exceptions.handle(e)
    finally:
        session.close()


@route_vendor.get(
    "/business/role",
    tags=["Role"],
    response_model=List[VendorRoleSchema],
    responses=makeExceptionResponses([exceptions.InvalidToken]),
    description="""
    Fetches a list of all vendor role across business.       
    Supports filtering by ID, name, permissions and metadata.   
    Supports filtering, sorting, and pagination.     
    Requires a valid vendor token.
    """,
)
async def fetch_role(
    qParam: QueryParamsForVE = Depends(), bearer=Depends(bearer_vendor)
):
    try:
        session = sessionMaker()
        token = validators.vendorToken(bearer.credentials, session)

        qParam = QueryParamsForEX(**qParam.model_dump(), business_id=token.business_id)
        return searchRole(session, qParam)
    except Exception as e:
        exceptions.handle(e)
    finally:
        session.close()
