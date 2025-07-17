from datetime import datetime
from enum import IntEnum
from typing import List, Optional
from fastapi import APIRouter, Depends, Query, Response, status, Form
from sqlalchemy.orm.session import Session
from fastapi.encoders import jsonable_encoder
from pydantic import BaseModel, Field

from app.api.bearer import bearer_executive, bearer_operator, bearer_vendor
from app.src.db import ExecutiveRole, OperatorRole, sessionMaker, Bus
from app.src import exceptions, validators, getters
from app.src.loggers import logEvent
from app.src.enums import BusStatus
from app.src.constants import REGEX_REGISTRATION_NUMBER
from app.src.functions import enumStr, makeExceptionResponses, updateIfChanged

route_executive = APIRouter()
route_vendor = APIRouter()
route_operator = APIRouter()


## Output Schema
class BusSchemaForVE(BaseModel):
    id: int
    company_id: int
    registration_number: str
    name: str
    capacity: int
    updated_on: Optional[datetime]
    created_on: datetime


class BusSchema(BusSchemaForVE):
    manufactured_on: datetime
    insurance_upto: Optional[datetime]
    pollution_upto: Optional[datetime]
    fitness_upto: Optional[datetime]
    road_tax_upto: Optional[datetime]
    status: int


## Input Forms
class CreateFormForOP(BaseModel):
    registration_number: str = Field(
        Form(regex=REGEX_REGISTRATION_NUMBER, max_length=16)
    )
    name: str = Field(Form(max_length=32))
    capacity: int = Field(Form(ge=1, le=120))
    manufactured_on: datetime = Field(Form())
    insurance_upto: datetime | None = Field(Form(default=None))
    pollution_upto: datetime | None = Field(Form(default=None))
    fitness_upto: datetime | None = Field(Form(default=None))
    road_tax_upto: datetime | None = Field(Form(default=None))
    status: BusStatus = Field(
        Form(description=enumStr(BusStatus), default=BusStatus.ACTIVE)
    )


class CreateFormForEX(CreateFormForOP):
    company_id: int = Field(Form())


class UpdateForm(BaseModel):
    id: int = Field(Form())
    name: str | None = Field(Form(max_length=32, default=None))
    capacity: int | None = Field(Form(ge=1, le=120, default=None))
    manufactured_on: datetime | None = Field(Form(default=None))
    insurance_upto: datetime | None = Field(Form(default=None))
    pollution_upto: datetime | None = Field(Form(default=None))
    fitness_upto: datetime | None = Field(Form(default=None))
    road_tax_upto: datetime | None = Field(Form(default=None))
    status: BusStatus | None = Field(Form(description=enumStr(BusStatus), default=None))


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


class QueryParams(BaseModel):
    # filters
    name: str | None = Field(Query(default=None))
    registration_number: str | None = Field(Query(default=None))
    # id based
    id: int | None = Field(Query(default=None))
    id_ge: int | None = Field(Query(default=None))
    id_le: int | None = Field(Query(default=None))
    id_list: List[int] | None = Field(Query(default=None))
    # capacity based
    capacity_ge: int | None = Field(Query(default=None))
    capacity_le: int | None = Field(Query(default=None))
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


class QueryParamsForVE(QueryParams):
    company_id: int | None = Field(Query(default=None))


class QueryParamsForOP(QueryParams):
    # filters
    status: BusStatus | None = Field(
        Query(default=None, description=enumStr(BusStatus))
    )
    # manufactured_on based
    manufactured_on_ge: datetime | None = Field(Query(default=None))
    manufactured_on_le: datetime | None = Field(Query(default=None))
    # insurance_upto based
    insurance_upto_ge: datetime | None = Field(Query(default=None))
    insurance_upto_le: datetime | None = Field(Query(default=None))
    # pollution_upto based
    pollution_upto_ge: datetime | None = Field(Query(default=None))
    pollution_upto_le: datetime | None = Field(Query(default=None))
    # fitness_upto based
    fitness_upto_ge: datetime | None = Field(Query(default=None))
    fitness_upto_le: datetime | None = Field(Query(default=None))
    # road_tax_upto based
    road_tax_upto_ge: datetime | None = Field(Query(default=None))
    road_tax_upto_le: datetime | None = Field(Query(default=None))


class QueryParamsForEX(QueryParamsForOP):
    company_id: int | None = Field(Query(default=None))


## Function
def updateBus(bus: Bus, fParam: UpdateForm):
    updateIfChanged(
        bus,
        fParam,
        [
            Bus.name.key,
            Bus.capacity.key,
            Bus.manufactured_on.key,
            Bus.insurance_upto.key,
            Bus.pollution_upto.key,
            Bus.fitness_upto.key,
            Bus.road_tax_upto.key,
            Bus.status.key,
        ],
    )


def searchBus(
    session: Session, qParam: QueryParamsForVE | QueryParamsForEX | QueryParamsForOP
) -> List[Bus]:
    query = session.query(Bus)

    # Filters
    if qParam.company_id is not None:
        query = query.filter(Bus.company_id == qParam.company_id)
    if qParam.name is not None:
        query = query.filter(Bus.name.ilike(f"%{qParam.name}%"))
    if qParam.status is not None:
        query = query.filter(Bus.status == qParam.status)
    # id based
    if qParam.id is not None:
        query = query.filter(Bus.id == qParam.id)
    if qParam.id_ge is not None:
        query = query.filter(Bus.id >= qParam.id_ge)
    if qParam.id_le is not None:
        query = query.filter(Bus.id <= qParam.id_le)
    if qParam.id_list is not None:
        query = query.filter(Bus.id.in_(qParam.id_list))
    # capacity based
    if qParam.capacity_ge is not None:
        query = query.filter(Bus.capacity >= qParam.capacity_ge)
    if qParam.capacity_le is not None:
        query = query.filter(Bus.capacity <= qParam.capacity_le)
    # manufactured_on based
    if qParam.manufactured_on_ge is not None:
        query = query.filter(Bus.manufactured_on >= qParam.manufactured_on_ge)
    if qParam.manufactured_on_le is not None:
        query = query.filter(Bus.manufactured_on <= qParam.manufactured_on_le)
    # insurance_upto based
    if qParam.insurance_upto_ge is not None:
        query = query.filter(Bus.insurance_upto >= qParam.insurance_upto_ge)
    if qParam.insurance_upto_le is not None:
        query = query.filter(Bus.insurance_upto <= qParam.insurance_upto_le)
    # pollution_upto based
    if qParam.pollution_upto_ge is not None:
        query = query.filter(Bus.pollution_upto >= qParam.pollution_upto_ge)
    if qParam.pollution_upto_le is not None:
        query = query.filter(Bus.pollution_upto <= qParam.pollution_upto_le)
    # fitness_upto based
    if qParam.fitness_upto_ge is not None:
        query = query.filter(Bus.fitness_upto >= qParam.fitness_upto_ge)
    if qParam.fitness_upto_le is not None:
        query = query.filter(Bus.fitness_upto <= qParam.fitness_upto_le)
    # road_tax_upto based
    if qParam.road_tax_upto_ge is not None:
        query = query.filter(Bus.road_tax_upto >= qParam.road_tax_upto_ge)
    if qParam.road_tax_upto_le is not None:
        query = query.filter(Bus.road_tax_upto <= qParam.road_tax_upto_le)
    # updated_on based
    if qParam.updated_on_ge is not None:
        query = query.filter(Bus.updated_on >= qParam.updated_on_ge)
    if qParam.updated_on_le is not None:
        query = query.filter(Bus.updated_on <= qParam.updated_on_le)
    # created_on based
    if qParam.created_on_ge is not None:
        query = query.filter(Bus.created_on >= qParam.created_on_ge)
    if qParam.created_on_le is not None:
        query = query.filter(Bus.created_on <= qParam.created_on_le)

    # Ordering
    orderingAttribute = getattr(Bus, OrderBy(qParam.order_by).name)
    if qParam.order_in == OrderIn.ASC:
        query = query.order_by(orderingAttribute.asc())
    else:
        query = query.order_by(orderingAttribute.desc())

    # Pagination
    query = query.offset(qParam.offset).limit(qParam.limit)
    return query.all()


## API endpoints [Executive]
@route_executive.post(
    "/company/bus",
    tags=["Bus"],
    response_model=BusSchema,
    status_code=status.HTTP_201_CREATED,
    responses=makeExceptionResponses(
        [exceptions.InvalidToken, exceptions.NoPermission]
    ),
    description="""
    Creates a new bus for a specified  company.     
    Only executive with `create_bus` permission can create bus.     
    Logs the bus account creation activity with the associated token.
    """,
)
async def create_bus(
    fParam: CreateFormForEX = Depends(),
    bearer=Depends(bearer_executive),
    request_info=Depends(getters.requestInfo),
):
    try:
        session = sessionMaker()
        token = validators.executiveToken(bearer.credentials, session)
        role = getters.executiveRole(token, session)
        validators.executivePermission(role, ExecutiveRole.create_bus)
        bus = Bus(
            company_id=fParam.company_id,
            name=fParam.name,
            registration_number=fParam.registration_number,
            capacity=fParam.capacity,
            manufactured_on=fParam.manufactured_on,
            insurance_upto=fParam.insurance_upto,
            pollution_upto=fParam.pollution_upto,
            fitness_upto=fParam.fitness_upto,
            road_tax_upto=fParam.road_tax_upto,
            status=fParam.status,
        )
        session.add(bus)
        session.commit()
        session.refresh(bus)

        busData = jsonable_encoder(bus)
        logEvent(token, request_info, busData)
        return busData
    except Exception as e:
        exceptions.handle(e)
    finally:
        session.close()


@route_executive.patch(
    "/company/bus",
    tags=["Bus"],
    response_model=BusSchema,
    responses=makeExceptionResponses(
        [exceptions.InvalidToken, exceptions.NoPermission, exceptions.InvalidIdentifier]
    ),
    description="""
    Updates an existing bus belonging to any company.       
    Only executives with `update_bus` permission can perform this operation.        
    Supports partial updates such as modifying the bus name or capacity.        
    Changes are saved only if the bus data has been modified.       
    Logs the bus updating activity with the associated token.
    """,
)
async def update_bus(
    fParam: UpdateForm = Depends(),
    bearer=Depends(bearer_executive),
    request_info=Depends(getters.requestInfo),
):
    try:
        session = sessionMaker()
        token = validators.executiveToken(bearer.credentials, session)
        role = getters.executiveRole(token, session)
        validators.executivePermission(role, ExecutiveRole.update_bus)

        bus = session.query(Bus).filter(Bus.id == fParam.id).first()
        if bus is None:
            raise exceptions.InvalidIdentifier()

        updateBus(bus, fParam)
        haveUpdates = session.is_modified(bus)
        if haveUpdates:
            session.commit()
            session.refresh(bus)

        busData = jsonable_encoder(bus)
        if haveUpdates:
            logEvent(token, request_info, busData)
        return busData
    except Exception as e:
        exceptions.handle(e)
    finally:
        session.close()


@route_executive.delete(
    "/company/bus",
    tags=["Bus"],
    status_code=status.HTTP_204_NO_CONTENT,
    responses=makeExceptionResponses(
        [exceptions.InvalidToken, exceptions.NoPermission]
    ),
    description="""
    Deletes an existing bus belonging to any company.       
    Only executives with `delete_bus` permission can perform this operation.    
    Validates the bus ID before deletion.       
    If the bus exists, it is permanently removed from the system.       
    Logs the deletion activity using the executive's token and request metadata.
    """,
)
async def delete_bus(
    fParam: DeleteForm = Depends(),
    bearer=Depends(bearer_executive),
    request_info=Depends(getters.requestInfo),
):
    try:
        session = sessionMaker()
        token = validators.executiveToken(bearer.credentials, session)
        role = getters.executiveRole(token, session)
        validators.executivePermission(role, ExecutiveRole.delete_bus)

        bus = session.query(Bus).filter(Bus.id == fParam.id).first()
        if bus is not None:
            session.delete(bus)
            session.commit()
            logEvent(token, request_info, jsonable_encoder(bus))
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    except Exception as e:
        exceptions.handle(e)
    finally:
        session.close()


@route_executive.get(
    "/company/bus",
    tags=["Bus"],
    responses=makeExceptionResponses([exceptions.InvalidToken]),
    response_model=List[BusSchema],
    description="""
    Fetches a list of all buses across companies.       
    Supports filtering by company ID, name, registration number and metadata.   
    Requires a valid executive token.
    """,
)
async def fetch_buses(
    qParam: QueryParamsForEX = Depends(),
    bearer=Depends(bearer_executive),
):
    try:
        session = sessionMaker()
        validators.executiveToken(bearer.credentials, session)

        return searchBus(session, qParam)
    except Exception as e:
        exceptions.handle(e)
    finally:
        session.close()


## API endpoints [Vendor]
@route_vendor.get(
    "/company/bus",
    tags=["Bus"],
    response_model=List[BusSchemaForVE],
    responses=makeExceptionResponses([exceptions.InvalidToken]),
    description="""
    Fetches a list of buses across companies based on provided query parameters.        
    Requires a valid vendor token for authentication.       
    Supports flexible filtering using query parameters such as bus ID, name, or company ID.
    """,
)
async def fetch_tokens(
    qParam: QueryParamsForVE = Depends(), bearer=Depends(bearer_vendor)
):
    try:
        session = sessionMaker()
        validators.vendorToken(bearer.credentials, session)

        qParam = QueryParamsForEX(
            **qParam.model_dump(),
            status=BusStatus.ACTIVE,
            manufactured_on_ge=None,
            manufactured_on_le=None,
            insurance_upto_ge=None,
            insurance_upto_le=None,
            pollution_upto_ge=None,
            pollution_upto_le=None,
            fitness_upto_ge=None,
            fitness_upto_le=None,
            road_tax_upto_ge=None,
            road_tax_upto_le=None,
        )
        return searchBus(session, qParam)
    except Exception as e:
        exceptions.handle(e)
    finally:
        session.close()


## API endpoints [Operator]
@route_operator.post(
    "/company/bus",
    tags=["Bus"],
    response_model=BusSchema,
    status_code=status.HTTP_201_CREATED,
    responses=makeExceptionResponses(
        [exceptions.InvalidToken, exceptions.NoPermission]
    ),
    description="""
    Creates a new bus for for the operator's own company.       
    Only operator with `create_bus` permission can create bus.      
    The company ID is derived from the token, not user input.       
    Logs the bus account creation activity with the associated token.
    """,
)
async def create_bus(
    fParam: CreateFormForOP = Depends(),
    bearer=Depends(bearer_operator),
    request_info=Depends(getters.requestInfo),
):
    try:
        session = sessionMaker()
        token = validators.operatorToken(bearer.credentials, session)
        role = getters.operatorRole(token, session)
        validators.operatorPermission(role, OperatorRole.create_bus)

        bus = Bus(
            company_id=token.company_id,
            registration_number=fParam.registration_number,
            name=fParam.name,
            capacity=fParam.capacity,
            manufactured_on=fParam.manufactured_on,
            insurance_upto=fParam.insurance_upto,
            pollution_upto=fParam.pollution_upto,
            fitness_upto=fParam.fitness_upto,
            road_tax_upto=fParam.road_tax_upto,
            status=fParam.status,
        )
        session.add(bus)
        session.commit()
        session.refresh(bus)

        busData = jsonable_encoder(bus)
        logEvent(token, request_info, busData)
        return busData
    except Exception as e:
        exceptions.handle(e)
    finally:
        session.close()


@route_operator.patch(
    "/company/bus",
    tags=["Bus"],
    response_model=BusSchema,
    responses=makeExceptionResponses(
        [exceptions.InvalidToken, exceptions.NoPermission, exceptions.InvalidIdentifier]
    ),
    description="""
    Updates an existing bus belonging to the operator's associated company.     
    Only operators with `update_bus` permission can perform this operation.     
    Validates the bus ID and ensures it belongs to the operator's company.      
    Supports partial updates such as modifying the bus name or capacity.        
    Changes are saved only if the bus data has been modified.       
    Logs the bus updating activity using the operator's token and request metadata.
    """,
)
async def update_bus(
    fParam: UpdateForm = Depends(),
    bearer=Depends(bearer_operator),
    request_info=Depends(getters.requestInfo),
):
    try:
        session = sessionMaker()
        token = validators.operatorToken(bearer.credentials, session)
        role = getters.operatorRole(token, session)
        validators.operatorPermission(role, OperatorRole.update_bus)

        bus = (
            session.query(Bus)
            .filter(Bus.id == fParam.id)
            .filter(Bus.company_id == token.company_id)
            .first()
        )
        if bus is None:
            raise exceptions.InvalidIdentifier()

        updateBus(bus, fParam)
        haveUpdates = session.is_modified(bus)
        if haveUpdates:
            session.commit()
            session.refresh(bus)

        busData = jsonable_encoder(bus)
        if haveUpdates:
            logEvent(token, request_info, busData)
        return busData
    except Exception as e:
        exceptions.handle(e)
    finally:
        session.close()


@route_operator.delete(
    "/company/bus",
    tags=["Bus"],
    status_code=status.HTTP_204_NO_CONTENT,
    responses=makeExceptionResponses(
        [exceptions.InvalidToken, exceptions.NoPermission]
    ),
    description="""
    Deletes an existing bus belonging to the operator's associated company.     
    Only operators with `delete_bus` permission can perform this operation.     
    Only bus owned by the operator's company can be deleted.        
    Logs the deletion activity using the operator's token and request metadata.
    """,
)
async def delete_bus(
    fParam: DeleteForm = Depends(),
    bearer=Depends(bearer_operator),
    request_info=Depends(getters.requestInfo),
):
    try:
        session = sessionMaker()
        token = validators.operatorToken(bearer.credentials, session)
        role = getters.operatorRole(token, session)
        validators.operatorPermission(role, OperatorRole.delete_bus)

        bus = (
            session.query(Bus)
            .filter(Bus.id == fParam.id)
            .filter(Bus.company_id == token.company_id)
            .first()
        )

        if bus is not None:
            session.delete(bus)
            session.commit()
            logEvent(token, request_info, jsonable_encoder(bus))
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    except Exception as e:
        exceptions.handle(e)
    finally:
        session.close()


@route_operator.get(
    "/company/bus",
    tags=["Bus"],
    response_model=List[BusSchema],
    responses=makeExceptionResponses([exceptions.InvalidToken]),
    description="""
    Fetches a list of buses associated with the operator's company.     
    Requires a valid operator token.        
    Supports filters like ID, registration number, name and creation timestamps.  
    """,
)
async def fetch_buses(
    qParam: QueryParamsForOP = Depends(), bearer=Depends(bearer_operator)
):
    try:
        session = sessionMaker()
        token = validators.operatorToken(bearer.credentials, session)

        qParam = QueryParamsForEX(**qParam.model_dump(), company_id=token.company_id)
        return searchBus(session, qParam)
    except Exception as e:
        exceptions.handle(e)
    finally:
        session.close()
