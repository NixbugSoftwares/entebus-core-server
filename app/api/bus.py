from fastapi import (
    APIRouter,
    Depends,
    status,
    Form,
)
from pydantic import BaseModel, Field
from fastapi.encoders import jsonable_encoder
from datetime import datetime

from app.api.bearer import bearer_executive, bearer_operator
from app.src.enums import BusStatus
from app.src.db import sessionMaker, Bus
from app.src import exceptions, schemas
from app.src.functions import (
    enumStr,
    getRequestInfo,
    logOperatorEvent,
    makeExceptionResponses,
    getOperatorToken,
    getOperatorRole,
    getExecutiveToken,
    getExecutiveRole,
    logExecutiveEvent,
)

route_operator = APIRouter()
route_executive = APIRouter()


class CreateBusFormForOp(BaseModel):
    registration_number: str = Field(Form(max_length=16))
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


class CreateBusFormForEx(CreateBusFormForOp):
    company_id: int = Field(Form())


## API endpoints [Operator]
@route_operator.post(
    "/company/bus",
    tags=["Bus"],
    response_model=schemas.Bus,
    status_code=status.HTTP_201_CREATED,
    responses=makeExceptionResponses(
        [
            exceptions.InvalidToken,
            exceptions.NoPermission,
        ]
    ),
    description="""
    Creates a new bus for a company.

    - Only operator with `create_bus` permission can create bus.
    - Logs the bus account creation activity with the associated token.
    """,
)
async def create_bus(
    fParam: CreateBusFormForOp = Depends(),
    bearer=Depends(bearer_operator),
    request_info=Depends(getRequestInfo),
):
    try:
        session = sessionMaker()
        token = getOperatorToken(bearer.credentials, session)
        if token is None:
            raise exceptions.InvalidToken()
        role = getOperatorRole(token, session)
        canCreateBus = bool(role and role.create_bus)
        if not canCreateBus:
            raise exceptions.NoPermission()

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
        logOperatorEvent(
            token,
            request_info,
            jsonable_encoder(bus),
        )
        return bus
    except Exception as e:
        exceptions.handle(e)
    finally:
        session.close()


@route_operator.patch(
    "/company/bus",
    tags=["Bus"],
    response_model=schemas.Bus,
    description="""
    Update bus.

    - Bus.
    """,
)
async def update_bus(
    bearer=Depends(bearer_operator),
    request_info=Depends(getRequestInfo),
):
    pass


@route_operator.get(
    "/company/bus",
    tags=["Bus"],
    response_model=schemas.Bus,
    description="""
    Retrieve bus.

    - Bus.
    """,
)
async def fetch_buses(
    bearer=Depends(bearer_operator),
):
    pass


@route_operator.delete(
    "/company/bus",
    tags=["Bus"],
    response_model=schemas.Bus,
    description="""
    Remove bus.

    - Bus.
    """,
)
async def delete_bus(
    bearer=Depends(bearer_operator),
    request_info=Depends(getRequestInfo),
):
    pass


## API endpoints [Executive]
@route_executive.post(
    "/company/bus",
    tags=["Bus"],
    response_model=schemas.Bus,
    status_code=status.HTTP_201_CREATED,
    responses=makeExceptionResponses(
        [
            exceptions.InvalidToken,
            exceptions.NoPermission,
        ]
    ),
    description="""
    Creates a new bus for a company.

    - Only executive with `create_bus` permission can create bus.
    - Logs the bus account creation activity with the associated token.
    """,
)
async def create_bus(
    fParam: CreateBusFormForEx = Depends(),
    bearer=Depends(bearer_executive),
    request_info=Depends(getRequestInfo),
):
    try:
        session = sessionMaker()
        token = getExecutiveToken(bearer.credentials, session)
        if token is None:
            raise exceptions.InvalidToken()
        role = getExecutiveRole(token, session)
        canCreateBus = bool(role and role.create_bus)
        if not canCreateBus:
            raise exceptions.NoPermission()

        bus = Bus(
            company_id=fParam.company_id,
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
        logExecutiveEvent(
            token,
            request_info,
            jsonable_encoder(bus),
        )
        return bus
    except Exception as e:
        exceptions.handle(e)
    finally:
        session.close()


@route_executive.patch(
    "/company/bus",
    tags=["Bus"],
    response_model=schemas.Bus,
    description="""
    Update bus.

    - Bus.
    """,
)
async def update_bus(
    bearer=Depends(bearer_executive),
    request_info=Depends(getRequestInfo),
):
    pass


@route_executive.get(
    "/company/bus",
    tags=["Bus"],
    response_model=schemas.Bus,
    description="""
    Retrieve bus.

    - Bus.
    """,
)
async def fetch_buses(
    bearer=Depends(bearer_executive),
):
    pass


@route_executive.delete(
    "/company/bus",
    tags=["Bus"],
    response_model=schemas.Bus,
    description="""
    Remove bus.

    - Bus.
    """,
)
async def delete_bus(
    bearer=Depends(bearer_executive),
    request_info=Depends(getRequestInfo),
):
    pass
