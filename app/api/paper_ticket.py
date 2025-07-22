from datetime import datetime
from enum import IntEnum
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, Query, status, Body
from fastapi.encoders import jsonable_encoder
from pydantic import BaseModel, Field
from sqlalchemy.orm.session import Session

from app.api.bearer import bearer_executive, bearer_operator
from app.src.db import LandmarkInRoute, PaperTicket, Service, Duty, sessionMaker
from app.src import exceptions, validators, getters
from app.src.loggers import logEvent
from app.src.functions import enumStr, makeExceptionResponses, promoteToParent
from app.src.dynamic_fare import v1

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
def searchPaperTicket(
    session: Session, qParam: QueryParamsForOP | QueryParamsForEX
) -> List[PaperTicket]:
    query = session.query(PaperTicket)

    # Filters
    if qParam.company_id is not None:
        query = query.filter(PaperTicket.company_id == qParam.company_id)
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
    Fetches a list of all paper tickets across companies.       
    Supports filtering like ID, amount range, ID range, sequence range and metadata.    
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

        return searchPaperTicket(session, qParam)
    except Exception as e:
        exceptions.handle(e)
    finally:
        session.close()


## API endpoints [Operator]
@route_operator.post(
    "/company/service/ticket/paper",
    tags=["Paper Ticket"],
    response_model=PaperTicketSchema,
    status_code=status.HTTP_201_CREATED,
    responses=makeExceptionResponses(
        [
            exceptions.InvalidToken,
            exceptions.UnknownValue(PaperTicket.service_id),
            exceptions.UnknownTicketType("ticket_type"),
            exceptions.InvalidFareFunction,
            exceptions.JSMemoryLimitExceeded,
            exceptions.JSTimeLimitExceeded,
        ]
    ),
    description="""
    Creates a new paper ticket for the operator duty and company.       
    The service and duty must be owned by the operator company.     
    The duty and service must be belong to the logged in operator.  
    The ticket_type -> name are closely bounded to the fare -> attributes -> ticket_type.  
    The distance will be calculated from the pickup point to the dropping point, not the user input.
    The amount will be calculated using the fare function and it will be cross-checked with the amount provided.    
    Requires a valid operator token.
    """,
)
async def create_paper_ticket(
    fParam: CreateForm = Depends(),
    bearer=Depends(bearer_operator),
    request_info=Depends(getters.requestInfo),
):
    try:
        session = sessionMaker()
        token = validators.operatorToken(bearer.credentials, session)

        service = (
            session.query(Service)
            .filter(Service.id == fParam.service_id)
            .filter(Service.company_id == token.company_id)
            .first()
        )
        if service is None:
            raise exceptions.UnknownValue(PaperTicket.service_id)

        duty = (
            session.query(Duty)
            .filter(Duty.id == fParam.duty_id)
            .filter(Duty.service_id == fParam.service_id)
            .filter(Duty.operator_id == token.operator_id)
            .first()
        )
        if duty is None:
            raise exceptions.UnknownValue(PaperTicket.duty_id)

        pickupLandmark = (
            session.query(LandmarkInRoute)
            .filter(
                LandmarkInRoute.route_id == service.route["id"],
                LandmarkInRoute.landmark_id == fParam.pickup_point,
            )
            .first()
        )
        if pickupLandmark is None:
            raise exceptions.UnknownValue(PaperTicket.pickup_point)

        droppingLandmark = (
            session.query(LandmarkInRoute)
            .filter(
                LandmarkInRoute.route_id == service.route["id"],
                LandmarkInRoute.landmark_id == fParam.dropping_point,
            )
            .first()
        )
        if droppingLandmark is None:
            raise exceptions.UnknownValue(PaperTicket.dropping_point)

        distance = (
            droppingLandmark.distance_from_start - pickupLandmark.distance_from_start
        )
        if droppingLandmark.distance_from_start < pickupLandmark.distance_from_start:
            raise exceptions.UnknownValue(PaperTicket.dropping_point)

        fParam.ticket_types = jsonable_encoder(fParam.ticket_types)
        totalFare = 0
        fareFunction = v1.DynamicFare(service.fare["function"])
        for ticketType in fParam.ticket_types:
            ticketTypeName = ticketType["name"]
            ticketTypeCount = ticketType["count"]
            if ticketTypeCount <= 0:
                raise exceptions.UnknownValue(PaperTicket.ticket_types)
            attributeTicketTypes = None
            fareTicketTypes = service.fare["attributes"]["ticket_types"]
            for attributeTicketType in fareTicketTypes:
                if attributeTicketType["name"] == ticketTypeName:
                    attributeTicketTypes = attributeTicketType
                    break
            if attributeTicketTypes is None:
                raise exceptions.UnknownTicketType(ticketTypeName)
            ticketPrice = fareFunction.evaluate(ticketTypeName, distance)
            totalFare += ticketPrice * ticketTypeCount

        if totalFare != fParam.amount:
            raise exceptions.UnknownValue(PaperTicket.amount)

        paperTicket = PaperTicket(
            service_id=fParam.service_id,
            company_id=token.company_id,
            duty_id=fParam.duty_id,
            sequence_id=fParam.sequence_id,
            ticket_types=fParam.ticket_types,
            pickup_point=fParam.pickup_point,
            dropping_point=fParam.dropping_point,
            extra=fParam.extra,
            amount=fParam.amount,
            distance=distance,
        )
        session.add(paperTicket)
        session.commit()
        session.refresh(paperTicket)

        paperTicketData = jsonable_encoder(paperTicket)
        logEvent(token, request_info, paperTicketData)
        return paperTicketData
    except Exception as e:
        exceptions.handle(e)
    finally:
        session.close()


@route_operator.get(
    "/company/service/ticket/paper",
    tags=["Paper Ticket"],
    response_model=List[PaperTicketSchema],
    responses=makeExceptionResponses([exceptions.InvalidToken]),
    description="""
    Fetches a list of all paper tickets for operator company.       
    Supports filtering like ID, amount range, ID range, sequence range and metadata.   
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

        qParam = promoteToParent(qParam, QueryParamsForEX, company_id=token.company_id)
        return searchPaperTicket(session, qParam)
    except Exception as e:
        exceptions.handle(e)
    finally:
        session.close()
