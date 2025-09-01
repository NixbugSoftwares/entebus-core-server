from datetime import datetime
from enum import IntEnum
from typing import List, Optional
from fastapi import APIRouter, Depends, Query, Response, status, Body
from sqlalchemy.orm.session import Session
from fastapi.encoders import jsonable_encoder
from pydantic import BaseModel, Field

from app.api.bearer import bearer_executive, bearer_operator
from app.src.db import (
    Company,
    ExecutiveRole,
    Fare,
    OperatorRole,
    Route,
    Schedule,
    sessionMaker,
    Bus,
)
from app.src import exceptions, validators, getters
from app.src.loggers import logEvent
from app.src.enums import Day, FareScope, TicketingMode, TriggeringMode
from app.src.constants import TMZ_PRIMARY
from app.src.functions import (
    enumStr,
    makeExceptionResponses,
    updateIfChanged,
    promoteToParent,
)
from app.src.urls import URL_SCHEDULE

route_executive = APIRouter()
route_operator = APIRouter()


## Output Schema
class ScheduleSchema(BaseModel):
    id: int
    company_id: int
    name: str
    description: Optional[str]
    route_id: Optional[int]
    fare_id: Optional[int]
    bus_id: Optional[int]
    frequency: Optional[List[int]]
    ticketing_mode: int
    triggering_mode: int
    next_trigger_on: Optional[datetime]
    last_trigger_on: Optional[datetime]
    trigger_till: Optional[datetime]
    updated_on: Optional[datetime]
    created_on: datetime


## Input Forms
class CreateFormForOP(BaseModel):
    name: str = Field(Body(max_length=128))
    description: str | None = Field(Body(max_length=2048, default=None))
    route_id: int = Field(Body())
    fare_id: int = Field(Body())
    bus_id: int = Field(Body())
    frequency: List[Day] | None = Field(Body(description=enumStr(Day), default=None))
    ticketing_mode: TicketingMode = Field(
        Body(description=enumStr(TicketingMode), default=TicketingMode.HYBRID)
    )
    triggering_mode: TriggeringMode = Field(
        Body(description=enumStr(TriggeringMode), default=TriggeringMode.AUTO)
    )
    trigger_till: datetime | None = Field(Body(default=None))


class CreateFormForEX(CreateFormForOP):
    company_id: int = Field(Body())


class UpdateForm(BaseModel):
    id: int = Field(Body())
    name: str | None = Field(Body(default=None, max_length=128))
    description: str | None = Field(Body(default=None, max_length=2048))
    route_id: int | None = Field(Body(default=None))
    fare_id: int | None = Field(Body(default=None))
    bus_id: int | None = Field(Body(default=None))
    frequency: List[Day] | None = Field(Body(default=None, description=enumStr(Day)))
    ticketing_mode: TicketingMode | None = Field(
        Body(default=None, description=enumStr(TicketingMode))
    )
    triggering_mode: TriggeringMode | None = Field(
        Body(default=None, description=enumStr(TriggeringMode))
    )
    trigger_till: datetime | None = Field(Body(default=None))


class DeleteForm(BaseModel):
    id: int = Field(Body())


## Query Parameters
class OrderIn(IntEnum):
    ASC = 1
    DESC = 2


class OrderBy(IntEnum):
    id = 1
    name = 2
    next_trigger_on = 3
    last_trigger_on = 4
    trigger_till = 5
    updated_on = 6
    created_on = 7


class QueryParamsForOP(BaseModel):
    name: str | None = Field(Query(default=None))
    description: str | None = Field(Query(default=None))
    route_id: int | None = Field(Query(default=None))
    fare_id: int | None = Field(Query(default=None))
    bus_id: int | None = Field(Query(default=None))
    frequency: List[Day] | None = Field(Query(default=None, description=enumStr(Day)))
    ticketing_mode: TicketingMode | None = Field(
        Query(default=None, description=enumStr(TicketingMode))
    )
    triggering_mode: TriggeringMode | None = Field(
        Query(default=None, description=enumStr(TriggeringMode))
    )
    # id based
    id: int | None = Field(Query(default=None))
    id_ge: int | None = Field(Query(default=None))
    id_le: int | None = Field(Query(default=None))
    id_list: List[int] | None = Field(Query(default=None))
    # next_trigger_on based
    next_trigger_on_ge: datetime | None = Field(Query(default=None))
    next_trigger_on_le: datetime | None = Field(Query(default=None))
    # last_trigger_on based
    last_trigger_on_ge: datetime | None = Field(Query(default=None))
    last_trigger_on_le: datetime | None = Field(Query(default=None))
    # trigger_till based
    trigger_till_ge: datetime | None = Field(Query(default=None))
    trigger_till_le: datetime | None = Field(Query(default=None))
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
def validateTriggerTill(fParam: CreateFormForOP | CreateFormForEX | UpdateForm):
    if fParam.trigger_till is not None:
        if fParam.trigger_till.astimezone(TMZ_PRIMARY) < datetime.now(TMZ_PRIMARY):
            raise exceptions.InvalidValue(Schedule.trigger_till)


def updateSchedule(session: Session, schedule: Schedule, fParam: UpdateForm):
    validateTriggerTill(fParam)
    updateIfChanged(
        schedule,
        fParam,
        [
            Schedule.name.key,
            Schedule.description.key,
            Schedule.frequency.key,
            Schedule.ticketing_mode.key,
            Schedule.triggering_mode.key,
            Schedule.trigger_till.key,
        ],
    )
    if fParam.route_id is not None and schedule.route_id != fParam.route_id:
        route = session.query(Route).filter(Route.id == fParam.route_id).first()
        if route is None:
            raise exceptions.UnknownValue(Schedule.route_id)
        if route.company_id != schedule.company_id:
            raise exceptions.InvalidAssociation(Schedule.route_id, Schedule.company_id)
        schedule.route_id = fParam.route_id
    if fParam.fare_id is not None and schedule.fare_id != fParam.fare_id:
        fare = session.query(Fare).filter(Fare.id == fParam.fare_id).first()
        if fare is None:
            raise exceptions.UnknownValue(Schedule.fare_id)
        if fare.scope != FareScope.GLOBAL:
            if fare.company_id != schedule.company_id:
                raise exceptions.InvalidAssociation(
                    Schedule.fare_id, Schedule.company_id
                )
        schedule.fare_id = fParam.fare_id
    if fParam.bus_id is not None and schedule.bus_id != fParam.bus_id:
        bus = session.query(Bus).filter(Bus.id == fParam.bus_id).first()
        if bus is None:
            raise exceptions.UnknownValue(Schedule.bus_id)
        if bus.company_id != schedule.company_id:
            raise exceptions.InvalidAssociation(Schedule.bus_id, Schedule.company_id)
        schedule.bus_id = fParam.bus_id


def searchSchedule(
    session: Session, qParam: QueryParamsForEX | QueryParamsForOP
) -> List[Schedule]:
    query = session.query(Schedule)

    # Filters
    if qParam.company_id is not None:
        query = query.filter(Schedule.company_id == qParam.company_id)
    if qParam.name is not None:
        query = query.filter(Schedule.name.ilike(f"%{qParam.name}%"))
    if qParam.description is not None:
        query = query.filter(Schedule.description.ilike(f"%{qParam.description}%"))
    if qParam.route_id is not None:
        query = query.filter(Schedule.route_id == qParam.route_id)
    if qParam.fare_id is not None:
        query = query.filter(Schedule.fare_id == qParam.fare_id)
    if qParam.bus_id is not None:
        query = query.filter(Schedule.bus_id == qParam.bus_id)
    if qParam.frequency is not None:
        query = query.filter(Schedule.frequency.op("&&")(qParam.frequency))
    if qParam.ticketing_mode is not None:
        query = query.filter(Schedule.ticketing_mode == qParam.ticketing_mode)
    if qParam.triggering_mode is not None:
        query = query.filter(Schedule.triggering_mode == qParam.triggering_mode)
    # id-based filters
    if qParam.id is not None:
        query = query.filter(Schedule.id == qParam.id)
    if qParam.id_ge is not None:
        query = query.filter(Schedule.id >= qParam.id_ge)
    if qParam.id_le is not None:
        query = query.filter(Schedule.id <= qParam.id_le)
    if qParam.id_list is not None:
        query = query.filter(Schedule.id.in_(qParam.id_list))
    # next_trigger_on based
    if qParam.next_trigger_on_ge is not None:
        query = query.filter(Schedule.next_trigger_on >= qParam.next_trigger_on_ge)
    if qParam.next_trigger_on_le is not None:
        query = query.filter(Schedule.next_trigger_on <= qParam.next_trigger_on_le)
    # last_trigger_on based
    if qParam.last_trigger_on_ge is not None:
        query = query.filter(Schedule.last_trigger_on >= qParam.last_trigger_on_ge)
    if qParam.last_trigger_on_le is not None:
        query = query.filter(Schedule.last_trigger_on <= qParam.last_trigger_on_le)
    # trigger_till based
    if qParam.trigger_till_ge is not None:
        query = query.filter(Schedule.trigger_till >= qParam.trigger_till_ge)
    if qParam.trigger_till_le is not None:
        query = query.filter(Schedule.trigger_till <= qParam.trigger_till_le)
    # updated_on based
    if qParam.updated_on_ge is not None:
        query = query.filter(Schedule.updated_on >= qParam.updated_on_ge)
    if qParam.updated_on_le is not None:
        query = query.filter(Schedule.updated_on <= qParam.updated_on_le)
    # created_on based
    if qParam.created_on_ge is not None:
        query = query.filter(Schedule.created_on >= qParam.created_on_ge)
    if qParam.created_on_le is not None:
        query = query.filter(Schedule.created_on <= qParam.created_on_le)

    # Ordering
    ordering_attr = getattr(Schedule, OrderBy(qParam.order_by).name)
    if qParam.order_in == OrderIn.ASC:
        query = query.order_by(ordering_attr.asc())
    else:
        query = query.order_by(ordering_attr.desc())

    # Pagination
    query = query.offset(qParam.offset).limit(qParam.limit)
    return query.all()


## API endpoints [Executive]
@route_executive.post(
    URL_SCHEDULE,
    tags=["Schedule"],
    response_model=ScheduleSchema,
    status_code=status.HTTP_201_CREATED,
    responses=makeExceptionResponses(
        [
            exceptions.InvalidToken,
            exceptions.NoPermission,
            exceptions.UnknownValue(Schedule.bus_id),
            exceptions.InvalidAssociation(Schedule.bus_id, Schedule.company_id),
        ]
    ),
    description="""
    Create a new schedule for a specified company.           
    Requires executive role with `create_schedule` permission.      
    In this bus_id, route_id must be associated with the company.       
    If fare_id is in Local scope, it must be associated with the company.   
    Trigger till must be a future date, it indicates the ending datetime of the schedule.   
    Log the schedule creation activity with the associated token.
    """,
)
async def create_schedule(
    fParam: CreateFormForEX = Depends(),
    bearer=Depends(bearer_executive),
    request_info=Depends(getters.requestInfo),
):
    try:
        session = sessionMaker()
        token = validators.executiveToken(bearer.credentials, session)
        role = getters.executiveRole(token, session)
        validators.executivePermission(role, ExecutiveRole.create_schedule)

        company = session.query(Company).filter(Company.id == fParam.company_id).first()
        if company is None:
            raise exceptions.UnknownValue(Schedule.company_id)
        bus = session.query(Bus).filter(Bus.id == fParam.bus_id).first()
        if bus is None:
            raise exceptions.UnknownValue(Schedule.bus_id)
        route = session.query(Route).filter(Route.id == fParam.route_id).first()
        if route is None:
            raise exceptions.UnknownValue(Schedule.route_id)
        fare = session.query(Fare).filter(Fare.id == fParam.fare_id).first()
        if fare is None:
            raise exceptions.UnknownValue(Schedule.fare_id)

        if bus.company_id != company.id:
            raise exceptions.InvalidAssociation(Schedule.bus_id, Schedule.company_id)
        if route.company_id != company.id:
            raise exceptions.InvalidAssociation(Schedule.route_id, Schedule.company_id)
        if fare.scope != FareScope.GLOBAL:
            if fare.company_id != company.id:
                raise exceptions.InvalidAssociation(
                    Schedule.fare_id, Schedule.company_id
                )
        validateTriggerTill(fParam)

        schedule = Schedule(
            company_id=fParam.company_id,
            name=fParam.name,
            description=fParam.description,
            route_id=fParam.route_id,
            fare_id=fParam.fare_id,
            bus_id=fParam.bus_id,
            frequency=fParam.frequency,
            ticketing_mode=fParam.ticketing_mode,
            triggering_mode=fParam.triggering_mode,
            trigger_till=fParam.trigger_till,
        )
        session.add(schedule)
        session.commit()
        session.refresh(schedule)

        scheduleData = jsonable_encoder(schedule)
        logEvent(token, request_info, scheduleData)
        return scheduleData
    except Exception as e:
        exceptions.handle(e)
    finally:
        session.close()


@route_executive.patch(
    URL_SCHEDULE,
    tags=["Schedule"],
    response_model=ScheduleSchema,
    responses=makeExceptionResponses(
        [
            exceptions.InvalidToken,
            exceptions.NoPermission,
            exceptions.InvalidIdentifier,
            exceptions.UnknownValue(Schedule.route_id),
            exceptions.InvalidAssociation(Schedule.bus_id, Schedule.company_id),
        ]
    ),
    description="""
    Update an existing schedule by ID.      
    Requires executive role with `update_schedule` permission.   
    In this bus_id, route_id must be associated with the company.       
    If fare_id is in Local scope, it must be associated with the company.    
    Trigger till must be a future date, it indicates the ending datetime of the schedule.   
    Log the schedule update activity with the associated token.
    """,
)
async def update_schedule(
    fParam: UpdateForm = Depends(),
    bearer=Depends(bearer_executive),
    request_info=Depends(getters.requestInfo),
):
    try:
        session = sessionMaker()
        token = validators.executiveToken(bearer.credentials, session)
        role = getters.executiveRole(token, session)
        validators.executivePermission(role, ExecutiveRole.update_schedule)

        schedule = session.query(Schedule).filter(Schedule.id == fParam.id).first()
        if schedule is None:
            raise exceptions.InvalidIdentifier()

        updateSchedule(session, schedule, fParam)
        haveUpdates = session.is_modified(schedule)
        if haveUpdates:
            session.commit()
            session.refresh(schedule)

        scheduleData = jsonable_encoder(schedule)
        if haveUpdates:
            logEvent(token, request_info, scheduleData)
        return scheduleData
    except Exception as e:
        exceptions.handle(e)
    finally:
        session.close()


@route_executive.delete(
    URL_SCHEDULE,
    tags=["Schedule"],
    status_code=status.HTTP_204_NO_CONTENT,
    responses=makeExceptionResponses(
        [exceptions.InvalidToken, exceptions.NoPermission]
    ),
    description="""
    Delete an existing schedule by ID.      
    Requires executive role with `delete_schedule` permission.      
    Deletes the schedule if it exists and logs the action.
    """,
)
async def delete_schedule(
    fParam: DeleteForm = Depends(),
    bearer=Depends(bearer_executive),
    request_info=Depends(getters.requestInfo),
):
    try:
        session = sessionMaker()
        token = validators.executiveToken(bearer.credentials, session)
        role = getters.executiveRole(token, session)
        validators.executivePermission(role, ExecutiveRole.delete_schedule)

        schedule = session.query(Schedule).filter(Schedule.id == fParam.id).first()
        if schedule is not None:
            session.delete(schedule)
            session.commit()
            logEvent(token, request_info, jsonable_encoder(schedule))
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    except Exception as e:
        exceptions.handle(e)
    finally:
        session.close()


@route_executive.get(
    URL_SCHEDULE,
    tags=["Schedule"],
    response_model=List[ScheduleSchema],
    responses=makeExceptionResponses([exceptions.InvalidToken]),
    description="""
    Fetch a list of all schedules across companies.     
    Only available to users with a valid executive token.       
    Supports filtering, sorting, and pagination.
    """,
)
async def fetch_schedule(
    qParam: QueryParamsForEX = Depends(), bearer=Depends(bearer_executive)
):
    try:
        session = sessionMaker()
        validators.executiveToken(bearer.credentials, session)

        return searchSchedule(session, qParam)
    except Exception as e:
        exceptions.handle(e)
    finally:
        session.close()


## API endpoints [Operator]
@route_operator.post(
    URL_SCHEDULE,
    tags=["Schedule"],
    response_model=ScheduleSchema,
    status_code=status.HTTP_201_CREATED,
    responses=makeExceptionResponses(
        [
            exceptions.InvalidToken,
            exceptions.NoPermission,
            exceptions.UnknownValue(Schedule.bus_id),
        ]
    ),
    description="""
    Create a new schedule for the operator's own company.       
    Requires operator role with `create_schedule` permission.       
    The company ID is derived from the token, not user input.       
    In this bus_id, route_id must be associated with the company.           
    If fare_id is in Local scope, it must be associated with the company.       
    Trigger till must be a future date, it indicates the ending datetime of the schedule.   
    Log the schedule creation activity with the associated token.
    """,
)
async def create_schedule(
    fParam: CreateFormForOP = Depends(),
    bearer=Depends(bearer_operator),
    request_info=Depends(getters.requestInfo),
):
    try:
        session = sessionMaker()
        token = validators.operatorToken(bearer.credentials, session)
        role = getters.operatorRole(token, session)
        validators.operatorPermission(role, OperatorRole.create_schedule)

        bus = (
            session.query(Bus)
            .filter(Bus.id == fParam.bus_id)
            .filter(Bus.company_id == token.company_id)
            .first()
        )
        if bus is None:
            raise exceptions.UnknownValue(Schedule.bus_id)
        route = (
            session.query(Route)
            .filter(Route.id == fParam.route_id)
            .filter(Route.company_id == token.company_id)
            .first()
        )
        if route is None:
            raise exceptions.UnknownValue(Schedule.route_id)
        fare = session.query(Fare).filter(Fare.id == fParam.fare_id).first()
        if fare is None:
            raise exceptions.UnknownValue(Schedule.fare_id)
        if fare.scope != FareScope.GLOBAL:
            if fare.company_id != token.company_id:
                raise exceptions.InvalidAssociation(
                    Schedule.fare_id, Schedule.company_id
                )
        validateTriggerTill(fParam)

        schedule = Schedule(
            company_id=token.company_id,
            name=fParam.name,
            description=fParam.description,
            route_id=fParam.route_id,
            fare_id=fParam.fare_id,
            bus_id=fParam.bus_id,
            frequency=fParam.frequency,
            ticketing_mode=fParam.ticketing_mode,
            triggering_mode=fParam.triggering_mode,
            trigger_till=fParam.trigger_till,
        )
        session.add(schedule)
        session.commit()
        session.refresh(schedule)

        scheduleData = jsonable_encoder(schedule)
        logEvent(token, request_info, scheduleData)
        return scheduleData
    except Exception as e:
        exceptions.handle(e)
    finally:
        session.close()


@route_operator.patch(
    URL_SCHEDULE,
    tags=["Schedule"],
    response_model=ScheduleSchema,
    responses=makeExceptionResponses(
        [
            exceptions.InvalidToken,
            exceptions.NoPermission,
            exceptions.InvalidIdentifier,
            exceptions.UnknownValue(Schedule.route_id),
            exceptions.InvalidAssociation(Schedule.bus_id, Schedule.company_id),
        ]
    ),
    description="""
    Update an existing schedule belonging to the operator's company.        
    Requires operator role with `update_schedule` permission.       
    Ensures the schedule is owned by the operator's company.        
    Trigger till must be a future date, it indicates the ending datetime of the schedule.   
    Log the schedule updating activity with the associated token.
    """,
)
async def update_schedule(
    fParam: UpdateForm = Depends(),
    bearer=Depends(bearer_operator),
    request_info=Depends(getters.requestInfo),
):
    try:
        session = sessionMaker()
        token = validators.operatorToken(bearer.credentials, session)
        role = getters.operatorRole(token, session)
        validators.operatorPermission(role, OperatorRole.update_schedule)

        schedule = (
            session.query(Schedule)
            .filter(Schedule.id == fParam.id)
            .filter(Schedule.company_id == token.company_id)
            .first()
        )
        if schedule is None:
            raise exceptions.InvalidIdentifier()

        updateSchedule(session, schedule, fParam)
        haveUpdates = session.is_modified(schedule)
        if haveUpdates:
            session.commit()
            session.refresh(schedule)

        scheduleData = jsonable_encoder(schedule)
        if haveUpdates:
            logEvent(token, request_info, scheduleData)
        return scheduleData
    except Exception as e:
        exceptions.handle(e)
    finally:
        session.close()


@route_operator.delete(
    URL_SCHEDULE,
    tags=["Schedule"],
    status_code=status.HTTP_204_NO_CONTENT,
    responses=makeExceptionResponses(
        [exceptions.InvalidToken, exceptions.NoPermission]
    ),
    description="""
    Delete an existing schedule by ID.          
    Requires operator role with `delete_schedule` permission.       
    Ensures the schedule is owned by the operator's company.        
    Log the schedule deletion activity with the associated token.
    """,
)
async def delete_schedule(
    fParam: DeleteForm = Depends(),
    bearer=Depends(bearer_operator),
    request_info=Depends(getters.requestInfo),
):
    try:
        session = sessionMaker()
        token = validators.operatorToken(bearer.credentials, session)
        role = getters.operatorRole(token, session)
        validators.operatorPermission(role, OperatorRole.delete_schedule)

        schedule = (
            session.query(Schedule)
            .filter(Schedule.id == fParam.id)
            .filter(Schedule.company_id == token.company_id)
            .first()
        )

        if schedule is not None:
            session.delete(schedule)
            session.commit()
            logEvent(token, request_info, jsonable_encoder(schedule))
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    except Exception as e:
        exceptions.handle(e)
    finally:
        session.close()


@route_operator.get(
    URL_SCHEDULE,
    tags=["Schedule"],
    response_model=List[ScheduleSchema],
    responses=makeExceptionResponses([exceptions.InvalidToken]),
    description="""
    Fetch a list of all schedules owned by the operator's company.          
    Only available to users with a valid operator token.        
    Supports filtering, sorting, and pagination.
    """,
)
async def fetch_schedule(
    qParam: QueryParamsForOP = Depends(), bearer=Depends(bearer_operator)
):
    try:
        session = sessionMaker()
        token = validators.operatorToken(bearer.credentials, session)

        qParam = promoteToParent(qParam, QueryParamsForEX, company_id=token.company_id)
        return searchSchedule(session, qParam)
    except Exception as e:
        exceptions.handle(e)
    finally:
        session.close()
