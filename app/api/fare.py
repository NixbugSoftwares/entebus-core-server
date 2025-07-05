from datetime import datetime
from enum import IntEnum
from typing import List, Optional, Dict, Any, Annotated
from fastapi import (
    APIRouter,
    Depends,
    Query,
    Response,
    status,
    Form,
    Body
)
from sqlalchemy.orm.session import Session
from fastapi.encoders import jsonable_encoder
from pydantic import BaseModel, Field, Json

from app.api.bearer import bearer_executive, bearer_operator, bearer_vendor
from app.src.db import (
    ExecutiveRole,
    Fare,
    OperatorRole,
    sessionMaker,
)
from app.src import exceptions, validators, getters
from app.src.loggers import logEvent
from app.src.enums import FareScope
from app.src.functions import enumStr, makeExceptionResponses

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
    name: str = Field(..., max_length=32)
    attributes: FareAttributes = Field(...)
    function: str = Field(..., max_length=2048)


class CreateFormForEX(CreateFormForOP):
    company_id: int | None = Field(default=None)
    scope: FareScope = Field(
        description=enumStr(FareScope), default=FareScope.GLOBAL)
    


class UpdateForm(BaseModel):
    id: int = Field(Form())
    name: str | None = Field(Form(default=None, max_length=32))
    attributes: Json | None = Field(Form(default=None))
    function: str | None = Field(Form(default=None, max_length=2048))


class DeleteForm(BaseModel):
    id: int = Field(Form())


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
    if fParam.name is not None and fParam.name != fare.name:
        fare.name = fParam.name
    if fParam.attributes is not None and fParam.attributes != fare.attributes:
        fare.attributes = fParam.attributes
    if fParam.function is not None and fParam.function != fare.function:
        fare.function = fParam.function
    FareAttributes.model_validate(fare.attributes)
    validators.fareFunction(function, fare.attributes)


def searchFare(
    session: Session, qParam: QueryParamsForOP | QueryParamsForEX
) -> List[Fare]:
    query = session.query(Fare)

    # Filters
    if qParam.name is not None:
        query = query.filter(Fare.name.ilike(f"%{qParam.name}%"))
    if qParam.company_id is not None:
        query = query.filter(Fare.company_id == qParam.company_id)
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
    "/company/fare",
    tags=["Fare"],
    response_model=FareSchema,
    status_code=status.HTTP_201_CREATED,
    responses=makeExceptionResponses(
        [
            exceptions.InvalidToken,
            exceptions.NoPermission,
        ]
    ),
    description="""
    Create a new fare in global scope or in local  scope for a  specified company.           
    Requires executive role with `create_fare` permission.    
    If the fare is in Local scope, it must be associated with the company.
    If the fare is in Global scope, company_id must be None.   
    Log the fare creation activity with the associated token.
    """,
)
async def create_fare(
    fParam: CreateFormForEX = Body(),
    bearer=Depends(bearer_executive),
    request_info=Depends(getters.requestInfo),
):
    try:
        session = sessionMaker()
        token = validators.executiveToken(bearer.credentials, session)
        role = getters.executiveRole(token, session)
        validators.executivePermission(role, ExecutiveRole.create_fare)

        fParam.attributes = fParam.attributes.model_dump()
        # FareAttributes.model_validate(fParam.attributes)
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
        logEvent(token, request_info, jsonable_encoder(fare))
        return fare
    except Exception as e:
        exceptions.handle(e)
    finally:
        session.close()


@route_executive.patch(
    "/company/fare",
    tags=["Fare"],
    response_model=FareSchema,
    responses=makeExceptionResponses(
        [
            exceptions.InvalidToken,
            exceptions.NoPermission,
            exceptions.InvalidIdentifier,
        ]
    ),
    description="""
    Updates an existing fare belonging to any company.       
    Only executives with `update_fare` permission can perform this operation.        
    Supports partial updates such as modifying the fare name or function.        
    Changes are saved only if the fare data has been modified.       
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
        haveUpdate = session.is_modified(fare)
        if haveUpdate:
            fare.version += 1
            session.commit()
            session.refresh(fare)
            logEvent(token, request_info, jsonable_encoder(fare))
        return fare
    except Exception as e:
        exceptions.handle(e)
    finally:
        session.close()


@route_executive.delete(
    "/company/fare",
    tags=["Fare"],
    status_code=status.HTTP_204_NO_CONTENT,
    responses=makeExceptionResponses(
        [exceptions.InvalidToken, exceptions.NoPermission]
    ),
    description="""
    Deletes an existing fare belonging to any company.       
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
    "/company/fare",
    tags=["Fare"],
    responses=makeExceptionResponses([exceptions.InvalidToken]),
    response_model=List[FareSchema],
    description="""
    Fetches a list of all fares across companies.       
    Supports filtering by company ID, name, registration number and metadata.   
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
    "/company/fare",
    tags=["Fare"],
    response_model=List[FareSchema],
    responses=makeExceptionResponses([exceptions.InvalidToken]),
    description="""
    Fetch a list of all fare across companies.   
    Only available to users with a valid vendor token.      
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
    "/company/fare",
    tags=["Fare"],
    response_model=FareSchema,
    status_code=status.HTTP_201_CREATED,
    responses=makeExceptionResponses(
        [exceptions.InvalidToken, exceptions.NoPermission]
    ),
    description="""
    Creates a new fare for for the operator's own company.       
    Only operator with `create_fare` permission can create fare.      
    The company ID is derived from the token, not user input.       
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

        FareAttributes.model_validate(fParam.attributes)
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
        logEvent(token, request_info, jsonable_encoder(fare))
        return fare
    except Exception as e:
        exceptions.handle(e)
    finally:
        session.close()


@route_operator.patch(
    "/company/fare",
    tags=["Fare"],
    response_model=FareSchema,
    responses=makeExceptionResponses(
        [
            exceptions.InvalidToken,
            exceptions.NoPermission,
            exceptions.InvalidIdentifier,
        ]
    ),
    description="""
    Updates an existing fare belonging to the operator's associated company.     
    Only operators with `update_fare` permission can perform this operation.     
    Validates the fare ID and ensures it belongs to the operator's company.             
    Changes are saved only if the fare data has been modified.       
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
        haveUpdated = session.is_modified(fare)
        if haveUpdated:
            fare.version += 1
            session.commit()
            session.refresh(fare)
            logEvent(token, request_info, jsonable_encoder(fare))
        return fare
    except Exception as e:
        exceptions.handle(e)
    finally:
        session.close()


@route_operator.delete(
    "/company/fare",
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


@route_operator.get(
    "/company/fare",
    tags=["Fare"],
    response_model=List[FareSchema],
    responses=makeExceptionResponses([exceptions.InvalidToken]),
    description="""
    Fetches a list of fares associated with the operator's company.     
    Requires a valid operator token.        
    Supports filters like ID, registration number, name and creation timestamps.  
    """,
)
async def fetch_fare(
    qParam: QueryParamsForOP = Depends(), bearer=Depends(bearer_operator)
):
    try:
        session = sessionMaker()
        token = validators.operatorToken(bearer.credentials, session)

        qParam = QueryParamsForEX(
            **qParam.model_dump(),
            company_id=token.company_id or None,
        )
        return searchFare(session, qParam)
    except Exception as e:
        exceptions.handle(e)
    finally:
        session.close()
