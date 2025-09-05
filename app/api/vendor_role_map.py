from datetime import datetime
from enum import IntEnum
from typing import List, Optional
from fastapi import APIRouter, Depends, Query, Response, status, Form
from fastapi.encoders import jsonable_encoder
from pydantic import BaseModel, Field
from sqlalchemy.orm.session import Session

from app.api.bearer import bearer_executive, bearer_vendor
from app.src.db import (
    VendorRole,
    ExecutiveRole,
    VendorRoleMap,
    Vendor,
    sessionMaker,
)
from app.src import exceptions, validators, getters
from app.src.loggers import logEvent
from app.src.functions import enumStr, fuseExceptionResponses, promoteToParent
from app.src.urls import URL_VENDOR_ROLE_MAP

route_executive = APIRouter()
route_vendor = APIRouter()


## Output Schema
class VendorRoleMapSchema(BaseModel):
    id: int
    business_id: int
    role_id: int
    vendor_id: int
    updated_on: Optional[datetime]
    created_on: datetime


class CreateForm(BaseModel):
    role_id: int = Field(Form())
    vendor_id: int = Field(Form())


class UpdateForm(BaseModel):
    id: int = Field(Form())
    role_id: int | None = Field(Form(default=None))


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
    # Filters
    role_id: int | None = Field(Query(default=None))
    vendor_id: int | None = Field(Query(default=None))
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
    business_id: int | None = Field(Query(default=None))


## Functions
def createRoleMap(role: VendorRole, vendor: Vendor):
    if role.business_id != vendor.business_id:
        raise exceptions.InvalidAssociation(
            VendorRoleMap.role_id, VendorRoleMap.business_id
        )
    return VendorRoleMap(
        role_id=role.id, vendor_id=vendor.id, business_id=vendor.business_id
    )


def updateRoleMap(session: Session, roleMap: VendorRoleMap, fParam: UpdateForm):
    if fParam.role_id is not None and roleMap.role_id != fParam.role_id:
        role = session.query(VendorRole).filter(VendorRole.id == fParam.role_id).first()
        if role is None:
            raise exceptions.UnknownValue(VendorRoleMap.role_id)
        if role.business_id != roleMap.business_id:
            raise exceptions.InvalidAssociation(
                VendorRoleMap.role_id, VendorRoleMap.business_id
            )
        roleMap.role_id = fParam.role_id


def searchRoleMap(
    session: Session, qParam: QueryParamsForVE | QueryParamsForEX
) -> List[VendorRoleMap]:
    query = session.query(VendorRoleMap)

    if qParam.role_id is not None:
        query = query.filter(VendorRoleMap.role_id == qParam.role_id)
    if qParam.vendor_id is not None:
        query = query.filter(VendorRoleMap.vendor_id == qParam.vendor_id)
    if qParam.business_id is not None:
        query = query.filter(VendorRoleMap.business_id == qParam.business_id)
    # id based
    if qParam.id is not None:
        query = query.filter(VendorRoleMap.id == qParam.id)
    if qParam.id_ge is not None:
        query = query.filter(VendorRoleMap.id >= qParam.id_ge)
    if qParam.id_le is not None:
        query = query.filter(VendorRoleMap.id <= qParam.id_le)
    if qParam.id_list is not None:
        query = query.filter(VendorRoleMap.id.in_(qParam.id_list))
    # updated_on based
    if qParam.updated_on_ge is not None:
        query = query.filter(VendorRoleMap.updated_on >= qParam.updated_on_ge)
    if qParam.updated_on_le is not None:
        query = query.filter(VendorRoleMap.updated_on <= qParam.updated_on_le)
    # created_on based
    if qParam.created_on_ge is not None:
        query = query.filter(VendorRoleMap.created_on >= qParam.created_on_ge)
    if qParam.created_on_le is not None:
        query = query.filter(VendorRoleMap.created_on <= qParam.created_on_le)

    # Ordering
    orderingAttribute = getattr(VendorRoleMap, OrderBy(qParam.order_by).name)
    if qParam.order_in == OrderIn.ASC:
        query = query.order_by(orderingAttribute.asc())
    else:
        query = query.order_by(orderingAttribute.desc())

    # Pagination
    query = query.offset(qParam.offset).limit(qParam.limit)
    return query.all()


## API endpoints [Executive]
@route_executive.post(
    URL_VENDOR_ROLE_MAP,
    tags=["Vendor Role Map"],
    response_model=VendorRoleMapSchema,
    status_code=status.HTTP_201_CREATED,
    responses=fuseExceptionResponses(
        [
            exceptions.InvalidToken(),
            exceptions.NoPermission(),
            exceptions.UnknownValue(VendorRoleMap.vendor_id),
            exceptions.InvalidAssociation(
                VendorRoleMap.role_id, VendorRoleMap.business_id
            ),
        ]
    ),
    description="""
    Assign a role to an vendor account.    
    Only authorized users with `update_ve_role` permission can create a new role map.    
    Log the role map creation activity with the associated token.
    """,
)
async def create_role_map(
    fParam: CreateForm = Depends(),
    bearer=Depends(bearer_executive),
    request_info=Depends(getters.requestInfo),
):
    try:
        session = sessionMaker()
        token = validators.executiveToken(bearer.credentials, session)
        role = getters.executiveRole(token, session)
        validators.executivePermission(role, ExecutiveRole.update_ve_role)

        vendor = session.query(Vendor).filter(Vendor.id == fParam.vendor_id).first()
        if vendor is None:
            raise exceptions.UnknownValue(VendorRoleMap.vendor_id)
        role = session.query(VendorRole).filter(VendorRole.id == fParam.role_id).first()
        if role is None:
            raise exceptions.UnknownValue(VendorRoleMap.role_id)
        roleMap = createRoleMap(role, vendor)

        session.add(roleMap)
        session.commit()
        session.refresh(roleMap)

        roleMapData = jsonable_encoder(roleMap)
        logEvent(token, request_info, roleMapData)
        return roleMapData
    except Exception as e:
        exceptions.handle(e)
    finally:
        session.close()


@route_executive.patch(
    URL_VENDOR_ROLE_MAP,
    tags=["Vendor Role Map"],
    response_model=VendorRoleMapSchema,
    responses=fuseExceptionResponses(
        [
            exceptions.InvalidToken(),
            exceptions.NoPermission(),
            exceptions.InvalidIdentifier(),
            exceptions.UnknownValue(VendorRoleMap.role_id),
            exceptions.InvalidAssociation(
                VendorRoleMap.role_id, VendorRoleMap.business_id
            ),
        ]
    ),
    description="""
    Updates an existing role maps.       
    Only executives with `update_ve_role` permission can perform this operation.    
    Support partial updates such as modifying the role_id.        
    Logs the role map updating activity with the associated token.
    """,
)
async def update_role_map(
    fParam: UpdateForm = Depends(),
    bearer=Depends(bearer_executive),
    request_info=Depends(getters.requestInfo),
):
    try:
        session = sessionMaker()
        token = validators.executiveToken(bearer.credentials, session)
        role = getters.executiveRole(token, session)
        validators.executivePermission(role, ExecutiveRole.update_ve_role)

        roleMap = (
            session.query(VendorRoleMap).filter(VendorRoleMap.id == fParam.id).first()
        )
        if roleMap is None:
            raise exceptions.InvalidIdentifier()

        updateRoleMap(session, roleMap, fParam)
        haveUpdates = session.is_modified(roleMap)
        if haveUpdates:
            session.commit()
            session.refresh(roleMap)

        roleMapData = jsonable_encoder(roleMap)
        if haveUpdates:
            logEvent(token, request_info, roleMapData)
        return roleMapData
    except Exception as e:
        exceptions.handle(e)
    finally:
        session.close()


@route_executive.delete(
    URL_VENDOR_ROLE_MAP,
    tags=["Vendor Role Map"],
    status_code=status.HTTP_204_NO_CONTENT,
    responses=fuseExceptionResponses(
        [exceptions.InvalidToken(), exceptions.NoPermission()]
    ),
    description="""
    Deletes an existing vendor role maps.       
    Only executives with `update_ve_role` permission can perform this operation.    
    Validates the role map ID before deletion.       
    If the mapping exists, it is permanently removed from the system.       
    Logs the deletion activity using the executive's token and request metadata.
    """,
)
async def delete_role_map(
    fParam: DeleteForm = Depends(),
    bearer=Depends(bearer_executive),
    request_info=Depends(getters.requestInfo),
):
    try:
        session = sessionMaker()
        token = validators.executiveToken(bearer.credentials, session)
        role = getters.executiveRole(token, session)
        validators.executivePermission(role, ExecutiveRole.update_ve_role)

        roleMap = (
            session.query(VendorRoleMap).filter(VendorRoleMap.id == fParam.id).first()
        )
        if roleMap is not None:
            session.delete(roleMap)
            session.commit()
            logEvent(token, request_info, jsonable_encoder(roleMap))
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    except Exception as e:
        exceptions.handle(e)
    finally:
        session.close()


@route_executive.get(
    URL_VENDOR_ROLE_MAP,
    tags=["Vendor Role Map"],
    response_model=List[VendorRoleMapSchema],
    responses=fuseExceptionResponses([exceptions.InvalidToken()]),
    description="""
    Fetches a list of all vendor role maps across business.       
    Supports filtering by ID and metadata.   
    Supports filtering, sorting, and pagination.     
    Requires a valid executive token.
    """,
)
async def fetch_role_map(
    qParam: QueryParamsForEX = Depends(), bearer=Depends(bearer_executive)
):
    try:
        session = sessionMaker()
        validators.executiveToken(bearer.credentials, session)

        return searchRoleMap(session, qParam)
    except Exception as e:
        exceptions.handle(e)
    finally:
        session.close()


## API endpoints [Vendor]
@route_vendor.post(
    URL_VENDOR_ROLE_MAP,
    tags=["Role Map"],
    response_model=VendorRoleMapSchema,
    status_code=status.HTTP_201_CREATED,
    responses=fuseExceptionResponses(
        [
            exceptions.InvalidToken(),
            exceptions.NoPermission(),
            exceptions.UnknownValue(VendorRoleMap.vendor_id),
            exceptions.InvalidAssociation(
                VendorRoleMap.role_id, VendorRoleMap.business_id
            ),
        ]
    ),
    description="""
    Assign a role to an vendor account, associated with the current vendor business.       
    Only authorized users with `update_role` permission can create a new role map.    
    Log the role map creation activity with the associated token.
    """,
)
async def create_role_map(
    fParam: CreateForm = Depends(),
    bearer=Depends(bearer_vendor),
    request_info=Depends(getters.requestInfo),
):
    try:
        session = sessionMaker()
        token = validators.vendorToken(bearer.credentials, session)
        role = getters.vendorRole(token, session)
        validators.vendorPermission(role, VendorRole.update_role)

        vendor = (
            session.query(Vendor)
            .filter(Vendor.id == fParam.vendor_id)
            .filter(Vendor.business_id == token.business_id)
            .first()
        )
        if vendor is None:
            raise exceptions.UnknownValue(VendorRoleMap.vendor_id)
        role = (
            session.query(VendorRole)
            .filter(VendorRole.id == fParam.role_id)
            .filter(VendorRole.business_id == token.business_id)
            .first()
        )
        if role is None:
            raise exceptions.UnknownValue(VendorRoleMap.role_id)
        roleMap = createRoleMap(role, vendor)

        session.add(roleMap)
        session.commit()
        session.refresh(roleMap)

        roleMapData = jsonable_encoder(roleMap)
        logEvent(token, request_info, roleMapData)
        return roleMapData
    except Exception as e:
        exceptions.handle(e)
    finally:
        session.close()


@route_vendor.patch(
    URL_VENDOR_ROLE_MAP,
    tags=["Role Map"],
    response_model=VendorRoleMapSchema,
    responses=fuseExceptionResponses(
        [
            exceptions.InvalidToken(),
            exceptions.NoPermission(),
            exceptions.InvalidIdentifier(),
            exceptions.UnknownValue(VendorRoleMap.role_id),
            exceptions.InvalidAssociation(
                VendorRoleMap.role_id, VendorRoleMap.business_id
            ),
        ]
    ),
    description="""
    Updates an existing role map, associated with the current vendor business.            
    Vendor with `update_role` permission can update other vendors role.  
    Support partial updates such as modifying the role_id.       
    Logs the role map update activity with the associated token.
    """,
)
async def update_role_map(
    fParam: UpdateForm = Depends(),
    bearer=Depends(bearer_vendor),
    request_info=Depends(getters.requestInfo),
):
    try:
        session = sessionMaker()
        token = validators.vendorToken(bearer.credentials, session)
        role = getters.vendorRole(token, session)
        validators.vendorPermission(role, VendorRole.update_role)

        roleMap = (
            session.query(VendorRoleMap)
            .filter(VendorRoleMap.id == fParam.id)
            .filter(VendorRoleMap.business_id == token.business_id)
            .first()
        )
        if roleMap is None:
            raise exceptions.InvalidIdentifier()

        updateRoleMap(session, roleMap, fParam)
        haveUpdates = session.is_modified(roleMap)
        if haveUpdates:
            session.commit()
            session.refresh(roleMap)

        roleMapData = jsonable_encoder(roleMap)
        if haveUpdates:
            logEvent(token, request_info, roleMapData)
        return roleMapData
    except Exception as e:
        exceptions.handle(e)
    finally:
        session.close()


@route_vendor.delete(
    URL_VENDOR_ROLE_MAP,
    tags=["Role Map"],
    status_code=status.HTTP_204_NO_CONTENT,
    responses=fuseExceptionResponses(
        [exceptions.InvalidToken(), exceptions.NoPermission()]
    ),
    description="""
    Deletes an existing vendor role map.       
    Only users with the `update_role` permission can delete vendor role maps.     
    Validates the role map ID before deletion.       
    If the role map exists, it is permanently removed from the system.       
    Logs the deletion activity using the vendor's token and request metadata.        
    """,
)
async def delete_role_map(
    fParam: DeleteForm = Depends(),
    bearer=Depends(bearer_vendor),
    request_info=Depends(getters.requestInfo),
):
    try:
        session = sessionMaker()
        token = validators.vendorToken(bearer.credentials, session)
        role = getters.vendorRole(token, session)
        validators.vendorPermission(role, VendorRole.update_role)

        roleMap = (
            session.query(VendorRoleMap)
            .filter(VendorRoleMap.id == fParam.id)
            .filter(VendorRoleMap.business_id == token.business_id)
            .first()
        )
        if roleMap is not None:
            session.delete(roleMap)
            session.commit()
            logEvent(token, request_info, jsonable_encoder(roleMap))
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    except Exception as e:
        exceptions.handle(e)
    finally:
        session.close()


@route_vendor.get(
    URL_VENDOR_ROLE_MAP,
    tags=["Role Map"],
    response_model=List[VendorRoleMapSchema],
    responses=fuseExceptionResponses([exceptions.InvalidToken()]),
    description="""
    Fetches a list of all vendor role maps for the current vendor business.       
    Supports filtering by ID and metadata.   
    Supports filtering, sorting, and pagination.     
    Requires a valid vendor token.
    """,
)
async def fetch_role_map(
    qParam: QueryParamsForVE = Depends(), bearer=Depends(bearer_vendor)
):
    try:
        session = sessionMaker()
        token = validators.vendorToken(bearer.credentials, session)

        qParam = promoteToParent(
            qParam, QueryParamsForEX, business_id=token.business_id
        )
        return searchRoleMap(session, qParam)
    except Exception as e:
        exceptions.handle(e)
    finally:
        session.close()
