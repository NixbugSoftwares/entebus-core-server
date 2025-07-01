from datetime import datetime, date
from enum import IntEnum
from typing import List, Optional, Dict
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

from app.api.bearer import bearer_executive, bearer_operator, bearer_vendor
from app.src.db import (
    Company,
    ExecutiveRole,
    Fare,
    OperatorRole,
    Route,
    Service,
    Bus,
    sessionMaker,
)
from app.src import exceptions, validators, getters
from app.src.loggers import logEvent
from app.src.enums import TicketingMode, ServiceStatus
from app.src.functions import enumStr, makeExceptionResponses

route_executive = APIRouter()
route_vendor = APIRouter()
route_operator = APIRouter()


## Output Schema
class ServiceSchema(BaseModel):
    id: int
    company_id: int
    route: Dict[str, int]
    fare: Dict[str, int]
    bus_id: int
    ticket_mode: int
    status: int
    starting_at: datetime
    ending_at: datetime
    public_key: str
    remark: Optional[str]
    started_on: Optional[datetime]
    finished_on: Optional[datetime]
    updated_on: Optional[datetime]
    created_on: datetime


## Input Forms
class CreateFormForOP(BaseModel):
    route: int = Field(Form())
    fare: int = Field(Form())
    bus_id: int = Field(Form())
    ticket_mode: TicketingMode = Field(
        Form(description=enumStr(TicketingMode), default=TicketingMode.HYBRID)
    )
    starting_at: date = Field(Form())


class CreateFormForEX(CreateFormForOP):
    company_id: int = Field(Form())


class UpdateForm(BaseModel):
    id: int = Field(Form())
    ticket_mode: TicketingMode | None = Field(
        Form(description=enumStr(TicketingMode), default=None)
    )
    status: ServiceStatus | None = Field(
        Form(description=enumStr(ServiceStatus), default=None)
    )
    remark: str | None = Field(Form(max_length=1024, default=None))


class DeleteForm(BaseModel):
    id: int = Field(Form())


## Query Params
class OrderIn(IntEnum):
    ASC = 1
    DESC = 2


class OrderBy(IntEnum):
    id = 1
    name = 2
    starting_at = 3
    ending_at = 4
    updated_on = 5
    created_on = 6


class QueryParamsForOP(BaseModel):
    # Filters
    bus_id: int | None = Field(Query(default=None))
    # route: Dict[str, int] | None = Field(Query(default=None))
    # fare: Dict[str, int] | None = Field(Query(default=None))
    ticket_mode: TicketingMode | None = Field(
        Query(default=None, description=enumStr(TicketingMode))
    )
    # id based
    id: int | None = Field(Query(default=None))
    id_ge: int | None = Field(Query(default=None))
    id_le: int | None = Field(Query(default=None))
    id_list: List[int] | None = Field(Query(default=None))
    # status based
    status: ServiceStatus | None = Field(
        Query(default=None, description=enumStr(ServiceStatus))
    )
    status_list: List[ServiceStatus] | None = Field(
        Query(default=None, description=enumStr(ServiceStatus))
    )
    # starting_at based
    starting_at_ge: datetime | None = Field(Query(default=None))
    starting_at_le: datetime | None = Field(Query(default=None))
    # ending_at based
    ending_at_ge: datetime | None = Field(Query(default=None))
    ending_at_le: datetime | None = Field(Query(default=None))
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


# Functions
