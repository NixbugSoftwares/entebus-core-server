from datetime import datetime, timedelta
from enum import IntEnum
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, Query, status, Form
from sqlalchemy.orm.session import Session
from fastapi.encoders import jsonable_encoder
from pydantic import BaseModel, Field

from app.api.bearer import bearer_executive, bearer_operator
from app.src.db import (
    Company,
    Fare,
    Route,
    Service,
    Bus,
    LandmarkInRoute,
    Landmark,
    Schedule,
    sessionMaker,
)
from app.src.constants import TMZ_SECONDARY
from app.src import exceptions, validators, getters
from app.src.loggers import logEvent
from app.src.redis import acquireLock, releaseLock

from app.src.enums import (
    TicketingMode,
    ServiceStatus,
    BusStatus,
    CompanyStatus,
    RouteStatus,
)
from app.src.functions import (
    enumStr,
    makeExceptionResponses,
    promoteToParent,
)
from app.src.digital_ticket import v1
from app.src.urls import URL_SCHEDULE_TRIGGER

route_executive = APIRouter()
route_vendor = APIRouter()
route_operator = APIRouter()


## Output Schema
class ServiceSchema(BaseModel):
    id: int
    company_id: int
    name: str
    route: Dict[str, Any]
    fare: Dict[str, Any]
    bus_id: int
    schedule_id: Optional[int]
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
class CreateForm(BaseModel):
    schedule_id: int = Field(Form())
    starting_at: datetime = Field(Form())


## Query Params
class OrderIn(IntEnum):
    ASC = 1
    DESC = 2


class OrderBy(IntEnum):
    id = 1
    name = 2
    schedule_id = 3
    starting_at = 4
    ending_at = 5
    updated_on = 6
    created_on = 7


class QueryParamsForOP(BaseModel):
    # Filters
    bus_id: int | None = Field(Query(default=None))
    ticket_mode: TicketingMode | None = Field(
        Query(default=None, description=enumStr(TicketingMode))
    )
    name: str | None = Field(Query(default=None))
    # status based
    status: ServiceStatus | None = Field(
        Query(default=None, description=enumStr(ServiceStatus))
    )
    status_list: List[ServiceStatus] | None = Field(
        Query(default=None, description=enumStr(ServiceStatus))
    )
    schedule_id: int | None = Field(Query(default=None))
    # id based
    id: int | None = Field(Query(default=None))
    id_ge: int | None = Field(Query(default=None))
    id_le: int | None = Field(Query(default=None))
    id_list: List[int] | None = Field(Query(default=None))
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


# Functions
def searchTriggerSchedules(
    session: Session, qParam: QueryParamsForOP | QueryParamsForEX
) -> List[Service]:
    query = session.query(Service).filter(Service.schedule_id != None)

    # Filters
    if qParam.bus_id is not None:
        query = query.filter(Service.bus_id == qParam.bus_id)
    if qParam.ticket_mode is not None:
        query = query.filter(Service.ticket_mode == qParam.ticket_mode)
    if qParam.company_id is not None:
        query = query.filter(Service.company_id == qParam.company_id)
    if qParam.name is not None:
        query = query.filter(Service.name.ilike(f"%{qParam.name}%"))
    if qParam.schedule_id is not None:
        query = query.filter(Service.schedule_id == qParam.schedule_id)
    # id-based filters
    if qParam.id is not None:
        query = query.filter(Service.id == qParam.id)
    if qParam.id_ge is not None:
        query = query.filter(Service.id >= qParam.id_ge)
    if qParam.id_le is not None:
        query = query.filter(Service.id <= qParam.id_le)
    if qParam.id_list is not None:
        query = query.filter(Service.id.in_(qParam.id_list))
    # status based
    if qParam.status is not None:
        query = query.filter(Service.status == qParam.status)
    if qParam.status_list is not None:
        query = query.filter(Service.status.in_(qParam.status_list))
    # starting_at based filters
    if qParam.starting_at_ge is not None:
        query = query.filter(Service.starting_at >= qParam.starting_at_ge)
    if qParam.starting_at_le is not None:
        query = query.filter(Service.starting_at <= qParam.starting_at_le)
    # ending_at-based filters
    if qParam.ending_at_ge is not None:
        query = query.filter(Service.ending_at >= qParam.ending_at_ge)
    if qParam.ending_at_le is not None:
        query = query.filter(Service.ending_at <= qParam.ending_at_le)
    # updated_on based filters
    if qParam.updated_on_ge is not None:
        query = query.filter(Service.updated_on >= qParam.updated_on_ge)
    if qParam.updated_on_le is not None:
        query = query.filter(Service.updated_on <= qParam.updated_on_le)
    # created_on based filters
    if qParam.created_on_ge is not None:
        query = query.filter(Service.created_on >= qParam.created_on_ge)
    if qParam.created_on_le is not None:
        query = query.filter(Service.created_on <= qParam.created_on_le)

    # Ordering
    orderingAttribute = getattr(Service, OrderBy(qParam.order_by).name)
    if qParam.order_in == OrderIn.ASC:
        query = query.order_by(orderingAttribute.asc())
    else:
        query = query.order_by(orderingAttribute.desc())

    # Pagination
    query = query.offset(qParam.offset).limit(qParam.limit)
    return query.all()


## API endpoints [Executive]
@route_executive.post(
    URL_SCHEDULE_TRIGGER,
    tags=["Trigger Schedule"],
    response_model=ServiceSchema,
    status_code=status.HTTP_201_CREATED,
    responses=makeExceptionResponses(
        [
            exceptions.InvalidToken,
            exceptions.NoPermission,
            exceptions.UnknownValue(Service.schedule_id),
            exceptions.InactiveResource(Bus),
            exceptions.InvalidRoute(),
            exceptions.InvalidValue(Service.starting_at),
            exceptions.LockAcquireTimeout,
        ]
    ),
    description="""
    Create a new service for a specified company.           
    Requires executive role with `create_service` permission.
    The bus must be in ACTIVE status. 
    The company must be in VERIFIED status.    
    The route must have at least two landmarks associated with it.        
    The first landmark must have a distance_from_start of 0, and both arrival_delta and departure_delta must also be 0.     
    For all intermediate landmarks (between the first and the last), the departure_delta must be greater than the arrival_delta.    
    The last landmark must have equal values for arrival_delta and departure_delta.    
    The service name is derived from the names of the route start_time + the first and last landmarks + the bus registration number, not from user input.             
    The ending_at is derived from the route last landmarks arrival_delta, not user input.     
    The service can be generated only for today and tomorrow.   
    The started_on will be set to current time when the operator start the duty, not user input.    
    The finished_on will be set to current time when the operators finish the service or when the statement is generated, not user input.   
    The service is created in the CREATED status by default.        
    Log the service creation activity with the associated token.
    """,
)
async def create_scheduled_trigger(
    fParam: CreateForm = Depends(),
    bearer=Depends(bearer_executive),
    request_info=Depends(getters.requestInfo),
):
    routeLock = None
    try:
        session = sessionMaker()
        token = validators.executiveToken(bearer.credentials, session)
        role = getters.executiveRole(token, session)
        if not (role.create_schedule | role.update_schedule):
            raise exceptions.NoPermission()

        schedule = (
            session.query(Schedule).filter(Schedule.id == fParam.schedule_id).first()
        )
        if schedule is None:
            raise exceptions.UnknownValue(Service.schedule_id)
        routeLock = acquireLock(Route.__tablename__, schedule.route_id)
        session.refresh(schedule)

        route = session.query(Route).filter(Route.id == schedule.route_id).first()
        bus = session.query(Bus).filter(Bus.id == schedule.bus_id).first()
        fare = session.query(Fare).filter(Fare.id == schedule.fare_id).first()
        company = (
            session.query(Company).filter(Company.id == schedule.company_id).first()
        )

        # Verify status
        if bus.status != BusStatus.ACTIVE:
            raise exceptions.InactiveResource(Bus)
        if company.status != CompanyStatus.VERIFIED:
            raise exceptions.InactiveResource(Company)
        if route.status != RouteStatus.VALID:
            raise exceptions.InactiveResource(Route)

        # Validate starting date
        ISTStartingAt = fParam.starting_at.astimezone(TMZ_SECONDARY)
        ISTDate = ISTStartingAt.date()
        currentDate = datetime.now(TMZ_SECONDARY).date()
        if ISTDate not in {currentDate, currentDate + timedelta(days=1)}:
            raise exceptions.InvalidValue(Service.starting_at)

        # Get starting_at and ending_at
        landmarksInRoute = (
            session.query(LandmarkInRoute)
            .filter(LandmarkInRoute.route_id == route.id)
            .order_by(LandmarkInRoute.distance_from_start.desc())
            .all()
        )
        if landmarksInRoute is None:
            raise exceptions.InvalidRoute()
        lastLandmark = landmarksInRoute[0]
        ending_at = fParam.starting_at + timedelta(seconds=lastLandmark.arrival_delta)

        firstLandmark = (
            session.query(Landmark)
            .join(LandmarkInRoute, Landmark.id == LandmarkInRoute.landmark_id)
            .filter(LandmarkInRoute.route_id == route.id)
            .order_by(LandmarkInRoute.distance_from_start.asc())
            .first()
        )
        lastLandmark = (
            session.query(Landmark)
            .join(LandmarkInRoute, Landmark.id == LandmarkInRoute.landmark_id)
            .filter(LandmarkInRoute.route_id == route.id)
            .order_by(LandmarkInRoute.distance_from_start.desc())
            .first()
        )
        if not firstLandmark or not lastLandmark:
            raise exceptions.InvalidAssociation(
                LandmarkInRoute.landmark_id, Service.route
            )

        # Create service name using IST time for display
        startingAt = ISTStartingAt.strftime("%Y-%m-%d %-I:%M %p")
        name = f"{startingAt} {firstLandmark.name} -> {lastLandmark.name} ({bus.registration_number})"

        # Generate route data
        routeData = jsonable_encoder(route)
        routeData["landmark"] = []
        for landmark in landmarksInRoute:
            routeData["landmark"].append(jsonable_encoder(landmark))

        # Generate fare data
        fareData = jsonable_encoder(fare)

        # Generate keys
        ticketCreator = v1.TicketCreator()
        privateKey = ticketCreator.getPEMprivateKeyString()
        publicKey = ticketCreator.getPEMpublicKeyString()

        service = Service(
            company_id=schedule.company_id,
            ticket_mode=schedule.ticketing_mode,
            bus_id=schedule.bus_id,
            schedule_id=fParam.schedule_id,
            name=name,
            route=routeData,
            fare=fareData,
            starting_at=fParam.starting_at,
            ending_at=ending_at,
            private_key=privateKey,
            public_key=publicKey,
        )
        session.add(service)
        session.commit()
        session.refresh(service)

        serviceData = jsonable_encoder(service, exclude={"private_key"})
        serviceLogData = serviceData.copy()
        serviceLogData.pop("public_key")
        logEvent(token, request_info, serviceLogData)
        return serviceData
    except Exception as e:
        exceptions.handle(e)
    finally:
        releaseLock(routeLock)
        session.close()


@route_executive.get(
    URL_SCHEDULE_TRIGGER,
    tags=["Trigger Schedule"],
    response_model=List[ServiceSchema],
    status_code=status.HTTP_201_CREATED,
    responses=makeExceptionResponses([exceptions.InvalidToken]),
    description="""
    Fetch a list of all services across companies.     
    Only available to users with a valid executive token.       
    Supports filtering, sorting, and pagination.
    """,
)
async def fetch_scheduled_trigger(
    qParam: QueryParamsForEX = Depends(), bearer=Depends(bearer_executive)
):
    try:
        session = sessionMaker()
        validators.executiveToken(bearer.credentials, session)

        return searchTriggerSchedules(session, qParam)
    except Exception as e:
        exceptions.handle(e)
    finally:
        session.close()


@route_operator.get(
    URL_SCHEDULE_TRIGGER,
    tags=["Trigger Schedule"],
    response_model=List[ServiceSchema],
    responses=makeExceptionResponses([exceptions.InvalidToken]),
    description="""
    Fetch a list of all services owned by the operator's company.          
    Only available to users with a valid operator token.        
    Supports filtering, sorting, and pagination.
    """,
)
async def fetch_scheduled_trigger(
    qParam: QueryParamsForOP = Depends(), bearer=Depends(bearer_operator)
):
    try:
        session = sessionMaker()
        token = validators.operatorToken(bearer.credentials, session)

        qParam = promoteToParent(qParam, QueryParamsForEX, company_id=token.company_id)
        return searchTriggerSchedules(session, qParam)
    except Exception as e:
        exceptions.handle(e)
    finally:
        session.close()
