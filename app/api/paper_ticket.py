from datetime import datetime
from enum import IntEnum
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, Query, status, Body
from fastapi.encoders import jsonable_encoder
from pydantic import BaseModel, Field
from sqlalchemy.orm.session import Session

from app.api.bearer import bearer_executive, bearer_operator
from app.src.db import (
    OperatorRole,
    ExecutiveRole,
    PaperTicket,
    Service,
    Duty,
    sessionMaker,
)
from app.src import exceptions, validators, getters
from app.src.loggers import logEvent
from app.src.functions import enumStr, makeExceptionResponses

route_executive = APIRouter()
route_operator = APIRouter()


## Output Schema
class TicketTypes(BaseModel):
    name: str
    count: int


class PaperTicketSchema(BaseModel):
    id: int
    service_id: int
    duty_id: int
    company_id: int
    sequence_id: int
    ticket_types: List[TicketTypes]
    pickup_point: int
    dropping_point: int
    extra: Dict[str, Any]
    distance: int
    amount: float
    updated_on: Optional[datetime]
    created_on: datetime


class CreateForm(BaseModel):
    service_id: int = Field(Body())
    duty_id: int = Field(Body())
    sequence_id: int = Field(Body())
    ticket_types: List[TicketTypes] = Field(Body())
    pickup_point: int = Field(Body())
    dropping_point: int = Field(Body())
    extra: Dict[str, Any] = Field(Body())
    amount: float = Field(Body())


## Query Parameters
class OrderIn(IntEnum):
    ASC = 1
    DESC = 2


class OrderBy(IntEnum):
    id = 1
    updated_on = 2
    created_on = 3


class QueryParamsForOP(BaseModel):
    # filters
    service_id: int | None = Field(Query(default=None))
    duty_id: int | None = Field(Query(default=None))
    pickup_point: int | None = Field(Query(default=None))
    dropping_point: int | None = Field(Query(default=None))
    # id based
    id: int | None = Field(Query(default=None))
    id_ge: int | None = Field(Query(default=None))
    id_le: int | None = Field(Query(default=None))
    id_list: List[int] | None = Field(Query(default=None))
    # sequence_id based
    sequence_id_ge: int | None = Field(Query(default=None))
    sequence_id_le: int | None = Field(Query(default=None))
    # amount based
    amount_ge: float | None = Field(Query(default=None))
    amount_le: float | None = Field(Query(default=None))
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


## Function
def searchPaperTickets(
    session: Session, qParam: QueryParamsForOP | QueryParamsForEX
) -> List[PaperTicket]:
    query = session.query(PaperTicket)

    # Filters
    if qParam.service_id is not None:
        query = query.filter(PaperTicket.service_id == qParam.service_id)
    if qParam.duty_id is not None:
        query = query.filter(PaperTicket.duty_id == qParam.duty_id)
    if qParam.pickup_point is not None:
        query = query.filter(PaperTicket.pickup_point == qParam.pickup_point)
    if qParam.dropping_point is not None:
        query = query.filter(PaperTicket.dropping_point == qParam.dropping_point)
    # id based filters
    if qParam.id is not None:
        query = query.filter(PaperTicket.id == qParam.id)
    if qParam.id_ge is not None:
        query = query.filter(PaperTicket.id >= qParam.id_ge)
    if qParam.id_le is not None:
        query = query.filter(PaperTicket.id <= qParam.id_le)
    if qParam.id_list is not None:
        query = query.filter(PaperTicket.id.in_(qParam.id_list))
    # sequence_id based filters
    if qParam.sequence_id_ge is not None:
        query = query.filter(PaperTicket.sequence_id >= qParam.sequence_id_ge)
    if qParam.sequence_id_le is not None:
        query = query.filter(PaperTicket.sequence_id <= qParam.sequence_id_le)
    # amount based filters
    if qParam.amount_ge is not None:
        query = query.filter(PaperTicket.amount >= qParam.amount_ge)
    if qParam.amount_le is not None:
        query = query.filter(PaperTicket.amount <= qParam.amount_le)
    # updated_on based filters
    if qParam.updated_on_ge is not None:
        query = query.filter(PaperTicket.updated_on >= qParam.updated_on_ge)
    if qParam.updated_on_le is not None:
        query = query.filter(PaperTicket.updated_on <= qParam.updated_on_le)
    # created_on based filters
    if qParam.created_on_ge is not None:
        query = query.filter(PaperTicket.created_on >= qParam.created_on_ge)
    if qParam.created_on_le is not None:
        query = query.filter(PaperTicket.created_on <= qParam.created_on_le)

    # Ordering
    ordering_attr = getattr(PaperTicket, OrderBy(qParam.order_by).name)
    if qParam.order_in == OrderIn.ASC:
        query = query.order_by(ordering_attr.asc())
    else:
        query = query.order_by(ordering_attr.desc())

    # Pagination
    query = query.offset(qParam.offset).limit(qParam.limit)
    return query.all()


## API endpoints [Executive]
@route_executive.get(
    "/company/service/ticket/paper",
    tags=["Paper Ticket"],
    response_model=List[PaperTicketSchema],
    responses=makeExceptionResponses([exceptions.InvalidToken]),
    description="""
    Fetches a list of all paper tickets across company.       
    Supports filtering by company ID, Id and metadata.  
    Supports filtering, sorting, and pagination.     
    Requires a valid executive token.
    """,
)
async def fetch_paper_ticket(
    qParam: QueryParamsForEX = Depends(),
    bearer=Depends(bearer_executive),
):
    try:
        session = sessionMaker()
        validators.executiveToken(bearer.credentials, session)

        return searchPaperTickets(session, qParam)
    except Exception as e:
        exceptions.handle(e)
    finally:
        session.close()


## API endpoints [Operator]
@route_operator.get(
    "/company/service/ticket/paper",
    tags=["Paper Ticket"],
    response_model=List[PaperTicketSchema],
    responses=makeExceptionResponses([exceptions.InvalidToken]),
    description="""
    Fetches a list of all paper tickets for operator company.       
    Supports filtering by ID, name, permissions and metadata.   
    Supports filtering, sorting, and pagination.     
    Requires a valid operator token.
    """,
)
async def fetch_paper_ticket(
    qParam: QueryParamsForOP = Depends(), bearer=Depends(bearer_operator)
):
    try:
        session = sessionMaker()
        token = validators.operatorToken(bearer.credentials, session)

        qParam = QueryParamsForEX(**qParam.model_dump(), company_id=token.company_id)
        return searchPaperTickets(session, qParam)
    except Exception as e:
        exceptions.handle(e)
    finally:
        session.close()
