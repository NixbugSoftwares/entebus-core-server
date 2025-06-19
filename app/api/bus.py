from fastapi import (
    APIRouter,
    Depends,
    status,
    Form,
)
from pydantic import BaseModel, Field
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
    registration_number: str = Field(Form(min_length=4, max_length=16))
    name: str = Field(Form(min_length=4, max_length=32))
    capacity: int = Field(Form())
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
    Create bus.

    - Bus.
    """,
)
async def create_bus(
    fParam: CreateBusFormForOp = Depends(),
    bearer=Depends(bearer_operator),
    request_info=Depends(getRequestInfo),
):
    pass


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
    bearer=Depends(bearer_executive),
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
    Create bus.

    - Bus.
    """,
)
async def create_bus(
    fParam: CreateBusFormForEx = Depends(),
    bearer=Depends(bearer_executive),
    request_info=Depends(getRequestInfo),
):
    pass


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
