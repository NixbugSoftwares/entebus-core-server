from datetime import datetime
from enum import IntEnum
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, Query, Response, status, Body
from sqlalchemy.orm.session import Session
from fastapi.encoders import jsonable_encoder
from pydantic import BaseModel, Field
from sqlalchemy import or_

from app.api.bearer import bearer_executive, bearer_operator, bearer_vendor
from app.src.db import ExecutiveRole, Fare, OperatorRole, sessionMaker
from app.src import exceptions, validators, getters
from app.src.loggers import logEvent
from app.src.enums import FareScope
from app.src.functions import (
    enumStr,
    makeExceptionResponses,
    updateIfChanged,
    promoteToParent,
)
from app.src.urls import URL_FARE

route_executive = APIRouter()
route_operator = APIRouter()
route_vendor = APIRouter()


## Output Schema
class TicketTypesInAttribute(BaseModel):
    id: int
    name: str


class FareAttributes(BaseModel):
    df_version: int
    ticket_types: List[TicketTypesInAttribute]
    currency_type: str
    distance_unit: str
    extra: Dict[str, Any]


class FareSchema(BaseModel):
    id: int
    company_id: Optional[int]
    version: int
    name: str
    attributes: FareAttributes
    function: str
    scope: FareScope
    updated_on: Optional[datetime]
    created_on: datetime


## Input Forms
class CreateFormForOP(BaseModel):
    name: str = Field(Body(max_length=32))
    attributes: FareAttributes = Field(Body())
    function: str = Field(Body(max_length=32768))


class CreateFormForEX(CreateFormForOP):
    company_id: int | None = Field(Body(default=None))
    scope: FareScope = Field(
        Body(description=enumStr(FareScope), default=FareScope.GLOBAL)
    )


class UpdateForm(BaseModel):
    id: int = Field(Body())
    name: str | None = Field(Body(default=None, max_length=32))
    attributes: FareAttributes | None = Field(Body(default=None))
    function: str | None = Field(Body(default=None, max_length=32768))


class DeleteForm(BaseModel):
    id: int = Field(Body())


## Query Parameters
class OrderIn(IntEnum):
    ASC = 1
    DESC = 2


class OrderBy(IntEnum):
    id = 1
    version = 2
    updated_on = 3
    created_on = 4


class QueryParamsForOP(BaseModel):
    name: str | None = Field(Query(default=None))
    scope: FareScope | None = Field(Query(default=None, description=enumStr(FareScope)))
    # id based
    id: int | None = Field(Query(default=None))
    id_ge: int | None = Field(Query(default=None))
    id_le: int | None = Field(Query(default=None))
    id_list: List[int] | None = Field(Query(default=None))
    # version based
    version: int | None = Field(Query(default=None))
    version_ge: int | None = Field(Query(default=None))
    version_le: int | None = Field(Query(default=None))
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


class QueryParamsForEX(QueryParamsForOP):
    company_id: int | None = Field(Query(default=None))


class QueryParamsForVE(QueryParamsForEX):
    pass


## Function
def updateFare(fare: Fare, fParam: UpdateForm):
    updateIfChanged(fare, fParam, [Fare.name.key, Fare.function.key])
    if fParam.attributes is not None and fParam.attributes != fare.attributes:
        fare.attributes = fParam.attributes.model_dump()
    validators.fareFunction(fare.function, fare.attributes)


def searchFare(
    session: Session, qParam: QueryParamsForOP | QueryParamsForEX
) -> List[Fare]:
    query = session.query(Fare)

    # Filters
    if qParam.name is not None:
        query = query.filter(Fare.name.ilike(f"%{qParam.name}%"))
    if qParam.company_id is not None:
        query = query.filter(
            or_(Fare.company_id == qParam.company_id, Fare.company_id == None)
        )
    if qParam.scope is not None:
        query = query.filter(Fare.scope == qParam.scope)
    # id based
    if qParam.id is not None:
        query = query.filter(Fare.id == qParam.id)
    if qParam.id_ge is not None:
        query = query.filter(Fare.id >= qParam.id_ge)
    if qParam.id_le is not None:
        query = query.filter(Fare.id <= qParam.id_le)
    if qParam.id_list is not None:
        query = query.filter(Fare.id.in_(qParam.id_list))
    # version based
    if qParam.version is not None:
        query = query.filter(Fare.version == qParam.version)
    if qParam.version_ge is not None:
        query = query.filter(Fare.version >= qParam.version_ge)
    if qParam.version_le is not None:
        query = query.filter(Fare.version <= qParam.version_le)
    # updated_on based
    if qParam.updated_on_ge is not None:
        query = query.filter(Fare.updated_on >= qParam.updated_on_ge)
    if qParam.updated_on_le is not None:
        query = query.filter(Fare.updated_on <= qParam.updated_on_le)
    # created_on based
    if qParam.created_on_ge is not None:
        query = query.filter(Fare.created_on >= qParam.created_on_ge)
    if qParam.created_on_le is not None:
        query = query.filter(Fare.created_on <= qParam.created_on_le)

    # Ordering
    ordering_attr = getattr(Fare, OrderBy(qParam.order_by).name)
    if qParam.order_in == OrderIn.ASC:
        query = query.order_by(ordering_attr.asc())
    else:
        query = query.order_by(ordering_attr.desc())

    # Pagination
    query = query.offset(qParam.offset).limit(qParam.limit)
    return query.all()


## API endpoints [Executive]
@route_executive.post(
    URL_FARE,
    tags=["Fare"],
    response_model=FareSchema,
    status_code=status.HTTP_201_CREATED,
    responses=makeExceptionResponses(
        [
            exceptions.InvalidToken,
            exceptions.NoPermission,
            exceptions.UnexpectedParameter(Fare.company_id),
            exceptions.MissingParameter(Fare.company_id),
            exceptions.UnknownTicketType("ticket_type"),
            exceptions.InvalidFareFunction,
        ]
    ),
    description="""
    Create a new fare in global scope or in local  scope for a specified company.           
    Requires executive role with `create_fare` permission.    
    If the fare is in Local scope, it must be associated with the company.
    If the fare is in Global scope, company_id must be None.   
    The DF function and DF attributes are always tightly coupled together.      
    The DF function is validated against the attributes.    
    The name of the JS function must be `getFare` and this function will accept exactly three arguments which are ticket_type, distance and extra.  
    The getFare function must return -1 if there is some logical or runtime error occurred during the function call.   
    Log the fare creation activity with the associated token.
    """,
)
async def create_fare(
    fParam: CreateFormForEX = Depends(),
    bearer=Depends(bearer_executive),
    request_info=Depends(getters.requestInfo),
):
    try:
        session = sessionMaker()
        token = validators.executiveToken(bearer.credentials, session)
        role = getters.executiveRole(token, session)
        validators.executivePermission(role, ExecutiveRole.create_fare)

        fParam.attributes = fParam.attributes.model_dump()
        validators.fareFunction(fParam.function, fParam.attributes)
        if fParam.scope == FareScope.GLOBAL and fParam.company_id is not None:
            raise exceptions.UnexpectedParameter(Fare.company_id)
        if fParam.scope == FareScope.LOCAL and fParam.company_id is None:
            raise exceptions.MissingParameter(Fare.company_id)
        fare = Fare(
            name=fParam.name,
            attributes=fParam.attributes,
            function=fParam.function,
            company_id=fParam.company_id,
            scope=fParam.scope,
        )
        session.add(fare)
        session.commit()
        session.refresh(fare)

        fareData = jsonable_encoder(fare)
        logEvent(token, request_info, fareData)
        return fareData
    except Exception as e:
        exceptions.handle(e)
    finally:
        session.close()


@route_executive.patch(
    URL_FARE,
    tags=["Fare"],
    response_model=FareSchema,
    responses=makeExceptionResponses(
        [
            exceptions.InvalidToken,
            exceptions.NoPermission,
            exceptions.InvalidIdentifier,
            exceptions.UnknownTicketType("ticket_type"),
            exceptions.InvalidFareFunction,
        ]
    ),
    description="""
    Updates an existing fare belonging to any company.       
    Only executives with `update_fare` permission can perform this operation.        
    Supports partial updates such as modifying the fare name or function.     
    The DF function and DF attributes are always tightly coupled together.      
    The DF function is validated against the attributes.    
    The name of the JS function must be `getFare` and this function will accept exactly three arguments which are ticket_type, distance and extra.  
    The getFare function must return -1 if there is some logical or runtime error occurred during the function call.      
    Changes are saved only if the fare data has been modified.     
    The version is automatically incremented, when the fare is modified.    
    Logs the fare updating activity with the associated token.
    """,
)
async def update_fare(
    fParam: UpdateForm = Depends(),
    bearer=Depends(bearer_executive),
    request_info=Depends(getters.requestInfo),
):
    try:
        session = sessionMaker()
        token = validators.executiveToken(bearer.credentials, session)
        role = getters.executiveRole(token, session)
        validators.executivePermission(role, ExecutiveRole.update_fare)

        fare = session.query(Fare).filter(Fare.id == fParam.id).first()
        if fare is None:
            raise exceptions.InvalidIdentifier()

        updateFare(fare, fParam)
        haveUpdates = session.is_modified(fare)
        if haveUpdates:
            fare.version += 1
            session.commit()
            session.refresh(fare)

        fareData = jsonable_encoder(fare)
        if haveUpdates:
            logEvent(token, request_info, fareData)
        return fareData
    except Exception as e:
        exceptions.handle(e)
    finally:
        session.close()


@route_executive.delete(
    URL_FARE,
    tags=["Fare"],
    status_code=status.HTTP_204_NO_CONTENT,
    responses=makeExceptionResponses(
        [exceptions.InvalidToken, exceptions.NoPermission]
    ),
    description="""
    Deletes an existing fare.       
    Only executives with `delete_fare` permission can perform this operation.    
    Validates the fare ID before deletion.       
    If the fare exists, it is permanently removed from the system.       
    Logs the deletion activity using the executive's token and request metadata.
    """,
)
async def delete_fare(
    fParam: DeleteForm = Depends(),
    bearer=Depends(bearer_executive),
    request_info=Depends(getters.requestInfo),
):
    try:
        session = sessionMaker()
        token = validators.executiveToken(bearer.credentials, session)
        role = getters.executiveRole(token, session)
        validators.executivePermission(role, ExecutiveRole.delete_fare)

        fare = session.query(Fare).filter(Fare.id == fParam.id).first()
        if fare is not None:
            session.delete(fare)
            session.commit()
            logEvent(token, request_info, jsonable_encoder(fare))
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    except Exception as e:
        exceptions.handle(e)
    finally:
        session.close()


@route_executive.get(
    URL_FARE,
    tags=["Fare"],
    response_model=List[FareSchema],
    responses=makeExceptionResponses([exceptions.InvalidToken]),
    description="""
    Fetches a list of all fares across Global and Local scope.       
    Supports filtering by company ID, name, scope and metadata.  
    Supports filtering, sorting, and pagination.     
    Requires a valid executive token.
    """,
)
async def fetch_fare(
    qParam: QueryParamsForEX = Depends(),
    bearer=Depends(bearer_executive),
):
    try:
        session = sessionMaker()
        validators.executiveToken(bearer.credentials, session)

        return searchFare(session, qParam)
    except Exception as e:
        exceptions.handle(e)
    finally:
        session.close()


## API endpoints [Vendor]
@route_vendor.get(
    URL_FARE,
    tags=["Fare"],
    response_model=List[FareSchema],
    responses=makeExceptionResponses([exceptions.InvalidToken]),
    description="""
    Fetch a list of all fare across  Global and Local scope.   
    Only available to users with a valid vendor token.     
    Supports filtering by company ID, name, scope and metadata.      
    Supports filtering, sorting, and pagination.
    """,
)
async def fetch_route(
    qParam: QueryParamsForVE = Depends(), bearer=Depends(bearer_vendor)
):
    try:
        session = sessionMaker()
        validators.vendorToken(bearer.credentials, session)

        return searchFare(session, qParam)
    except Exception as e:
        exceptions.handle(e)
    finally:
        session.close()


## API endpoints [Operator]
@route_operator.post(
    URL_FARE,
    tags=["Fare"],
    response_model=FareSchema,
    status_code=status.HTTP_201_CREATED,
    responses=makeExceptionResponses(
        [
            exceptions.InvalidToken,
            exceptions.NoPermission,
            exceptions.UnknownTicketType("ticket_type"),
            exceptions.InvalidFareFunction,
        ]
    ),
    description="""
    Creates a new fare for for the operator's own company.       
    Only operator with `create_fare` permission can create fare.      
    The company ID is derived from the token, not user input.    
    The scope of the fare is Local by default, not user input. 
    The DF function and DF attributes are always tightly coupled together.      
    The DF function is validated against the attributes.    
    The name of the JS function must be `getFare` and this function will accept exactly three arguments which are ticket_type, distance and extra.  
    The getFare function must return -1 if there is some logical or runtime error occurred during the function call.          
    Logs the fare account creation activity with the associated token.
    """,
)
async def create_fare(
    fParam: CreateFormForOP = Depends(),
    bearer=Depends(bearer_operator),
    request_info=Depends(getters.requestInfo),
):
    try:
        session = sessionMaker()
        token = validators.operatorToken(bearer.credentials, session)
        role = getters.operatorRole(token, session)
        validators.operatorPermission(role, OperatorRole.create_fare)

        fParam.attributes = fParam.attributes.model_dump()
        validators.fareFunction(fParam.function, fParam.attributes)
        fare = Fare(
            name=fParam.name,
            attributes=fParam.attributes,
            function=fParam.function,
            company_id=token.company_id,
            scope=FareScope.LOCAL,
        )
        session.add(fare)
        session.commit()
        session.refresh(fare)

        fareData = jsonable_encoder(fare)
        logEvent(token, request_info, fareData)
        return fareData
    except Exception as e:
        exceptions.handle(e)
    finally:
        session.close()


@route_operator.patch(
    URL_FARE,
    tags=["Fare"],
    response_model=FareSchema,
    responses=makeExceptionResponses(
        [
            exceptions.InvalidToken,
            exceptions.NoPermission,
            exceptions.InvalidIdentifier,
            exceptions.UnknownTicketType("ticket_type"),
            exceptions.InvalidFareFunction,
        ]
    ),
    description="""
    Updates an existing fare belonging to the operator's associated company.     
    Only operators with `update_fare` permission can perform this operation.     
    Validates the fare ID and ensures it belongs to the operator's company.             
    Changes are saved only if the fare data has been modified.       
    The DF function and DF attributes are always tightly coupled together.      
    The DF function is validated against the attributes.    
    The name of the JS function must be `getFare` and this function will accept exactly three arguments which are ticket_type, distance and extra.  
    The getFare function must return -1 if there is some logical or runtime error occurred during the function call.   
    The version is automatically incremented, when the fare is modified.    
    Logs the fare updating activity using the operator's token and request metadata.
    """,
)
async def update_fare(
    fParam: UpdateForm = Depends(),
    bearer=Depends(bearer_operator),
    request_info=Depends(getters.requestInfo),
):
    try:
        session = sessionMaker()
        token = validators.operatorToken(bearer.credentials, session)
        role = getters.operatorRole(token, session)
        validators.operatorPermission(role, OperatorRole.update_fare)

        fare = (
            session.query(Fare)
            .filter(Fare.id == fParam.id)
            .filter(Fare.company_id == token.company_id)
            .first()
        )
        if fare is None:
            raise exceptions.InvalidIdentifier()

        updateFare(fare, fParam)
        haveUpdates = session.is_modified(fare)
        if haveUpdates:
            fare.version += 1
            session.commit()
            session.refresh(fare)

        fareData = jsonable_encoder(fare)
        if haveUpdates:
            logEvent(token, request_info, fareData)
        return fareData
    except Exception as e:
        exceptions.handle(e)
    finally:
        session.close()


@route_operator.delete(
    URL_FARE,
    tags=["Fare"],
    status_code=status.HTTP_204_NO_CONTENT,
    responses=makeExceptionResponses(
        [exceptions.InvalidToken, exceptions.NoPermission]
    ),
    description="""
    Deletes an existing fare belonging to the operator's associated company.     
    Only operators with `delete_fare` permission can perform this operation.     
    Only fare owned by the operator's company can be deleted.        
    Logs the deletion activity using the operator's token and request metadata.
    """,
)
async def delete_fare(
    fParam: DeleteForm = Depends(),
    bearer=Depends(bearer_operator),
    request_info=Depends(getters.requestInfo),
):
    try:
        session = sessionMaker()
        token = validators.operatorToken(bearer.credentials, session)
        role = getters.operatorRole(token, session)
        validators.operatorPermission(role, OperatorRole.delete_fare)

        fare = (
            session.query(Fare)
            .filter(Fare.id == fParam.id)
            .filter(Fare.company_id == token.company_id)
            .first()
        )
        if fare is not None:
            session.delete(fare)
            session.commit()
            logEvent(token, request_info, jsonable_encoder(fare))
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    except Exception as e:
        exceptions.handle(e)
    finally:
        session.close()


@route_operator.get(
    URL_FARE,
    tags=["Fare"],
    response_model=List[FareSchema],
    responses=makeExceptionResponses([exceptions.InvalidToken]),
    description="""
    Fetches a list of fares associated with the operator's company and in global scope.     
    Requires a valid operator token.        
    Supports filters like ID, scope, name and creation timestamps.  
    Supports filtering, sorting, and pagination.
    """,
)
async def fetch_fare(
    qParam: QueryParamsForOP = Depends(), bearer=Depends(bearer_operator)
):
    try:
        session = sessionMaker()
        token = validators.operatorToken(bearer.credentials, session)

        qParam = promoteToParent(qParam, QueryParamsForEX, company_id=token.company_id)
        return searchFare(session, qParam)
    except Exception as e:
        exceptions.handle(e)
    finally:
        session.close()
