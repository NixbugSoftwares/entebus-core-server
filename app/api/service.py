from datetime import datetime, date, timedelta
from enum import IntEnum
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, Query, Response, status, Form
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
    LandmarkInRoute,
    Landmark,
    sessionMaker,
)
from app.src.constants import TMZ_PRIMARY, TMZ_SECONDARY
from app.src import exceptions, validators, getters
from app.src.loggers import logEvent
from app.src.enums import TicketingMode, ServiceStatus, FareScope, BusStatus
from app.src.functions import enumStr, makeExceptionResponses, updateIfChanged
from app.src.digital_ticket import v1

route_executive = APIRouter()
route_vendor = APIRouter()
route_operator = APIRouter()


## Output Schema
class ServiceSchemaForVE(BaseModel):
    id: int
    company_id: int
    name: str
    route: Dict[str, Any]
    fare: Dict[str, Any]
    bus_id: int
    ticket_mode: int
    status: int
    starting_at: datetime
    ending_at: datetime
    remark: Optional[str]
    started_on: Optional[datetime]
    finished_on: Optional[datetime]
    updated_on: Optional[datetime]
    created_on: datetime


class ServiceSchema(ServiceSchemaForVE):
    public_key: str


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


class QueryParams(BaseModel):
    # Filters
    bus_id: int | None = Field(Query(default=None))
    ticket_mode: TicketingMode | None = Field(
        Query(default=None, description=enumStr(TicketingMode))
    )
    name: str | None = Field(Query(default=None))
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


class QueryParamsForOP(QueryParams):
    # status based
    status: ServiceStatus | None = Field(
        Query(default=None, description=enumStr(ServiceStatus))
    )
    status_list: List[ServiceStatus] | None = Field(
        Query(default=None, description=enumStr(ServiceStatus))
    )


class QueryParamsForEX(QueryParamsForOP):
    company_id: int | None = Field(Query(default=None))


class QueryParamsForVE(QueryParams):
    company_id: int | None = Field(Query(default=None))


# Functions
def validateStartingDate(starting_at: date):
    if starting_at < date.today():
        raise exceptions.InvalidValue(Service.starting_at)
    if starting_at != date.today() and starting_at != (
        date.today() + timedelta(days=1)
    ):
        raise exceptions.InvalidValue(Service.starting_at)


def getServiceName(
    session: Session, route: Route, bus: Bus, starting_at: datetime
) -> str:
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
        raise exceptions.InvalidAssociation(LandmarkInRoute.landmark_id, Service.route)
    UTCtime = starting_at.replace(tzinfo=TMZ_PRIMARY)
    ISTtime = UTCtime.astimezone(TMZ_SECONDARY)
    startingAt = ISTtime.strftime("%Y-%m-%d %-I:%M %p")
    return f"{startingAt} {firstLandmark.name} -> {lastLandmark.name} ({bus.registration_number})"


def updateService(service: Service, fParam: UpdateForm):
    serviceStatusTransition = {
        ServiceStatus.CREATED: [],
        ServiceStatus.STARTED: [ServiceStatus.TERMINATED, ServiceStatus.ENDED],
        ServiceStatus.TERMINATED: [ServiceStatus.STARTED],
        ServiceStatus.ENDED: [ServiceStatus.STARTED],
        ServiceStatus.AUDITED: [],
    }
    updateIfChanged(service, fParam, [Service.ticket_mode.key, Service.remark.key])
    if fParam.status is not None and service.status != fParam.status:
        validators.stateTransition(
            serviceStatusTransition, service.status, fParam.status, Service.status
        )
        service.status = fParam.status


def searchService(
    session: Session, qParam: QueryParamsForOP | QueryParamsForEX | QueryParamsForVE
) -> List[Service]:
    query = session.query(Service)

    # Filters
    if qParam.bus_id is not None:
        query = query.filter(Service.bus_id == qParam.bus_id)
    if qParam.ticket_mode is not None:
        query = query.filter(Service.ticket_mode == qParam.ticket_mode)
    if qParam.company_id is not None:
        query = query.filter(Service.company_id == qParam.company_id)
    if qParam.name is not None:
        query = query.filter(Service.name.ilike(f"%{qParam.name}%"))
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
    "/company/service",
    tags=["Service"],
    response_model=ServiceSchema,
    status_code=status.HTTP_201_CREATED,
    responses=makeExceptionResponses(
        [
            exceptions.InvalidToken,
            exceptions.NoPermission,
            exceptions.UnknownValue(Service.bus_id),
            exceptions.InvalidAssociation(Service.fare, Service.company_id),
            exceptions.InactiveResource(Bus),
            exceptions.InvalidRoute(),
            exceptions.InvalidValue(Service.starting_at),
        ]
    ),
    description="""
    Create a new service for a specified company.           
    Requires executive role with `create_service` permission.   
    In this bus_id, route_id must be associated with the company_id.       
    If fare_id is in Local scope, it must be associated with the company_id.
    The bus must be in active status.    
    The route must have at least two landmarks associated with it.        
    The first landmark must have a distance_from_start of 0, and both arrival_delta and departure_delta must also be 0.     
    For all intermediate landmarks (between the first and the last), the departure_delta must be greater than the arrival_delta.    
    The last landmark must have equal values for arrival_delta and departure_delta.    
    The route name is derived from the names of the first and last landmarks + the route start_time, not from user input.      
    The starting_at is derived from the route start_time, not user input.           
    The ending_at is derived from the route last landmarks arrival_delta, not user input.     
    The service is created in the CREATED status by default.        
    Log the service creation activity with the associated token.
    """,
)
async def create_service(
    fParam: CreateFormForEX = Depends(),
    bearer=Depends(bearer_executive),
    request_info=Depends(getters.requestInfo),
):
    try:
        session = sessionMaker()
        token = validators.executiveToken(bearer.credentials, session)
        role = getters.executiveRole(token, session)
        validators.executivePermission(role, ExecutiveRole.create_service)

        company = session.query(Company).filter(Company.id == fParam.company_id).first()
        if company is None:
            raise exceptions.UnknownValue(Service.company_id)
        bus = session.query(Bus).filter(Bus.id == fParam.bus_id).first()
        if bus is None:
            raise exceptions.UnknownValue(Service.bus_id)
        route = session.query(Route).filter(Route.id == fParam.route).first()
        if route is None:
            raise exceptions.UnknownValue(Service.route)
        fare = session.query(Fare).filter(Fare.id == fParam.fare).first()
        if fare is None:
            raise exceptions.UnknownValue(Service.fare)

        if bus.company_id != company.id:
            raise exceptions.InvalidAssociation(Service.bus_id, Service.company_id)
        if route.company_id != company.id:
            raise exceptions.InvalidAssociation(Service.route, Service.company_id)
        validators.landmarkInRoute(route.id, session)
        if fare.scope != FareScope.GLOBAL:
            if fare.company_id != company.id:
                raise exceptions.InvalidAssociation(Service.fare, Service.company_id)

        if bus.status != BusStatus.ACTIVE:
            raise exceptions.InactiveResource(Bus)
        validateStartingDate(fParam.starting_at)

        landmarksInRoute = (
            session.query(LandmarkInRoute)
            .filter(LandmarkInRoute.route_id == route.id)
            .order_by(LandmarkInRoute.distance_from_start.desc())
            .all()
        )
        if landmarksInRoute is None:
            raise exceptions.InvalidRoute()
        lastLandmark = landmarksInRoute[0]
        fParam.starting_at = datetime.combine(fParam.starting_at, route.start_time)
        ending_at = fParam.starting_at + timedelta(seconds=lastLandmark.arrival_delta)

        name = getServiceName(session, route, bus, fParam.starting_at)

        routeData = jsonable_encoder(route)
        routeData["landmark"] = []
        for landmark in landmarksInRoute:
            routeData["landmark"].append(jsonable_encoder(landmark))

        fareData = jsonable_encoder(fare)
        ticketCreator = v1.TicketCreator()
        privateKey = ticketCreator.getPEMprivateKeyString()
        publicKey = ticketCreator.getPEMpublicKeyString()

        service = Service(
            company_id=fParam.company_id,
            name=name,
            bus_id=fParam.bus_id,
            route=routeData,
            fare=fareData,
            starting_at=fParam.starting_at,
            ending_at=ending_at,
            ticket_mode =fParam.ticket_mode,
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
        session.close()


@route_executive.patch(
    "/company/service",
    tags=["Service"],
    response_model=ServiceSchema,
    responses=makeExceptionResponses(
        [
            exceptions.InvalidToken,
            exceptions.NoPermission,
            exceptions.InvalidIdentifier,
            exceptions.InvalidStateTransition("status"),
        ]
    ),
    description="""
    Update an existing service by ID.      
    Requires executive role with `update_service` permission.       
    The status=AUDITED and STARTED is not accepted by user input.   
    Log the service update activity with the associated token.      

    Allowed status transitions:
        STARTED ↔ TERMINATED
        STARTED ↔ ENDED
    """,
)
async def update_service(
    fParam: UpdateForm = Depends(),
    bearer=Depends(bearer_executive),
    request_info=Depends(getters.requestInfo),
):
    try:
        session = sessionMaker()
        token = validators.executiveToken(bearer.credentials, session)
        role = getters.executiveRole(token, session)
        validators.executivePermission(role, ExecutiveRole.update_service)

        service = session.query(Service).filter(Service.id == fParam.id).first()
        if service is None:
            raise exceptions.InvalidIdentifier()

        updateService(service, fParam)
        haveUpdates = session.is_modified(service)
        if haveUpdates:
            session.commit()
            session.refresh(service)

        serviceData = jsonable_encoder(service, exclude={"private_key"})
        serviceLogData = serviceData.copy()
        serviceLogData.pop("public_key")
        if haveUpdates:
            logEvent(token, request_info, serviceLogData)
        return serviceData
    except Exception as e:
        exceptions.handle(e)
    finally:
        session.close()


@route_executive.delete(
    "/company/service",
    tags=["Service"],
    status_code=status.HTTP_204_NO_CONTENT,
    responses=makeExceptionResponses(
        [
            exceptions.InvalidToken,
            exceptions.NoPermission,
            exceptions.DataInUse(Service),
        ]
    ),
    description="""
    Delete an existing service by ID.      
    Requires executive role with `delete_service` permission.   
    Service can not be deleted if there are tickets associated with it.    
    Service can not be deleted if there are not in CREATED status.      
    Deletes the service if it exists and logs the action.
    """,
)
async def delete_service(
    fParam: DeleteForm = Depends(),
    bearer=Depends(bearer_executive),
    request_info=Depends(getters.requestInfo),
):
    try:
        session = sessionMaker()
        token = validators.executiveToken(bearer.credentials, session)
        role = getters.executiveRole(token, session)
        validators.executivePermission(role, ExecutiveRole.delete_service)

        service = session.query(Service).filter(Service.id == fParam.id).first()
        if service and service.status != ServiceStatus.CREATED:
            raise exceptions.DataInUse(Service)
        if service is not None:
            session.delete(service)
            session.commit()
            logEvent(
                token,
                request_info,
                jsonable_encoder(service, exclude={"private_key", "public_key"}),
            )
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    except Exception as e:
        exceptions.handle(e)
    finally:
        session.close()


@route_executive.get(
    "/company/service",
    tags=["Service"],
    response_model=List[ServiceSchema],
    responses=makeExceptionResponses([exceptions.InvalidToken]),
    description="""
    Fetch a list of all services across companies.     
    Only available to users with a valid executive token.       
    Supports filtering, sorting, and pagination.
    """,
)
async def fetch_service(
    qParam: QueryParamsForEX = Depends(), bearer=Depends(bearer_executive)
):
    try:
        session = sessionMaker()
        validators.executiveToken(bearer.credentials, session)

        return searchService(session, qParam)
    except Exception as e:
        exceptions.handle(e)
    finally:
        session.close()


## API endpoints [Vendor]
@route_vendor.get(
    "/company/service",
    tags=["Service"],
    response_model=List[ServiceSchemaForVE],
    responses=makeExceptionResponses([exceptions.InvalidToken]),
    description="""
    Fetch a list of all service  which are in CREATED or STARTED status across companies.   
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

        qParam = QueryParamsForEX(
            **qParam.model_dump(),
            status_list=[ServiceStatus.CREATED, ServiceStatus.STARTED],
            status=None,
        )
        return searchService(session, qParam)
    except Exception as e:
        exceptions.handle(e)
    finally:
        session.close()


## API endpoints [Operator]
@route_operator.post(
    "/company/service",
    tags=["Service"],
    response_model=ServiceSchema,
    status_code=status.HTTP_201_CREATED,
    responses=makeExceptionResponses(
        [
            exceptions.InvalidToken,
            exceptions.NoPermission,
            exceptions.UnknownValue(Service.bus_id),
            exceptions.InvalidAssociation(Service.fare, Service.company_id),
            exceptions.InactiveResource(Bus),
            exceptions.InvalidRoute(),
            exceptions.InvalidValue(Service.starting_at),
        ]
    ),
    description="""
    Create a new service for the operator's own company.	          
    Requires operator role with `create_service` permission.    
    The company ID is derived from the token, not user input.    
    In this bus_id, route_id must be associated with the operator's own company.        
    If fare_id is in Local scope, it must be associated with the operator's own company.       
    The bus must be in active status.   
    The route must have at least two landmarks associated with it.        
    The first landmark must have a distance_from_start of 0, and both arrival_delta and departure_delta must also be 0.     
    For all intermediate landmarks (between the first and the last), the departure_delta must be greater than the arrival_delta.    
    The last landmark must have equal values for arrival_delta and departure_delta.    
    The route name is derived from the names of the first and last landmarks + the route start_time, not from user input.         
    The starting_at is derived from the route start_time, not user input.       
    The ending_at is derived from the route last landmarks arrival_delta, not user input.       
    The service is created in the CREATED status by default.        
    Log the service creation activity with the associated token.
    """,
)
async def create_service(
    fParam: CreateFormForOP = Depends(),
    bearer=Depends(bearer_operator),
    request_info=Depends(getters.requestInfo),
):
    try:
        session = sessionMaker()
        token = validators.operatorToken(bearer.credentials, session)
        role = getters.operatorRole(token, session)
        validators.operatorPermission(role, OperatorRole.create_service)

        bus = (
            session.query(Bus)
            .filter(Bus.id == fParam.bus_id)
            .filter(Bus.company_id == token.company_id)
            .first()
        )
        if bus is None:
            raise exceptions.UnknownValue(Service.bus_id)
        route = (
            session.query(Route)
            .filter(Route.id == fParam.route)
            .filter(Route.company_id == token.company_id)
            .first()
        )
        if route is None:
            raise exceptions.UnknownValue(Service.route)
        validators.landmarkInRoute(route.id, session)
        fare = session.query(Fare).filter(Fare.id == fParam.fare).first()
        if fare and fare.scope != FareScope.GLOBAL:
            if fare.company_id != token.company_id:
                raise exceptions.InvalidAssociation(Service.fare, Service.company_id)

        if bus.status != BusStatus.ACTIVE:
            raise exceptions.InactiveResource(Bus)
        validateStartingDate(fParam.starting_at)

        landmarksInRoute = (
            session.query(LandmarkInRoute)
            .filter(LandmarkInRoute.route_id == route.id)
            .order_by(LandmarkInRoute.distance_from_start.desc())
            .all()
        )
        if landmarksInRoute is None:
            raise exceptions.InvalidRoute()
        lastLandmark = landmarksInRoute[0]
        fParam.starting_at = datetime.combine(fParam.starting_at, route.start_time)
        ending_at = fParam.starting_at + timedelta(seconds=lastLandmark.arrival_delta)

        name = getServiceName(session, route, bus, fParam.starting_at)

        routeData = jsonable_encoder(route)
        routeData["landmark"] = []
        for landmark in landmarksInRoute:
            routeData["landmark"].append(jsonable_encoder(landmark))

        fareData = jsonable_encoder(fare)
        ticketCreator = v1.TicketCreator()
        privateKey = ticketCreator.getPEMprivateKeyString()
        publicKey = ticketCreator.getPEMpublicKeyString()

        service = Service(
            company_id=token.company_id,
            name=name,
            bus_id=fParam.bus_id,
            route=routeData,
            fare=fareData,
            starting_at=fParam.starting_at,
            ending_at=ending_at,
            ticket_mode =fParam.ticket_mode,
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
        session.close()


@route_operator.patch(
    "/company/service",
    tags=["Service"],
    response_model=ServiceSchema,
    responses=makeExceptionResponses(
        [
            exceptions.InvalidToken,
            exceptions.NoPermission,
            exceptions.InvalidIdentifier,
            exceptions.InvalidStateTransition("status"),
        ]
    ),
    description="""
    Update an existing service belonging to the operator's company.        
    Requires operator role with `update_service` permission.              
    The status=AUDITED and STARTED is not accepted by user input.   
    Log the service updating activity with the associated token.    

    Allowed status transitions:
        STARTED ↔ TERMINATED
        STARTED ↔ ENDED
    """,
)
async def update_service(
    fParam: UpdateForm = Depends(),
    bearer=Depends(bearer_operator),
    request_info=Depends(getters.requestInfo),
):
    try:
        session = sessionMaker()
        token = validators.operatorToken(bearer.credentials, session)
        role = getters.operatorRole(token, session)
        validators.operatorPermission(role, OperatorRole.update_service)

        service = (
            session.query(Service)
            .filter(Service.id == fParam.id)
            .filter(Service.company_id == token.company_id)
            .first()
        )
        if service is None:
            raise exceptions.InvalidIdentifier()

        updateService(service, fParam)
        haveUpdates = session.is_modified(service)
        if haveUpdates:
            session.commit()
            session.refresh(service)

        serviceData = jsonable_encoder(service, exclude={"private_key"})
        serviceLogData = serviceData.copy()
        serviceLogData.pop("public_key")
        if haveUpdates:
            logEvent(token, request_info, serviceLogData)
        return serviceData
    except Exception as e:
        exceptions.handle(e)
    finally:
        session.close()


@route_operator.delete(
    "/company/service",
    tags=["Service"],
    status_code=status.HTTP_204_NO_CONTENT,
    responses=makeExceptionResponses(
        [
            exceptions.InvalidToken,
            exceptions.NoPermission,
            exceptions.DataInUse(Service),
        ]
    ),
    description="""
    Delete an existing service by ID.          
    Requires operator role with `delete_service` permission.       
    Ensures the service is owned by the operator's company.  
    Service can not be deleted if there are tickets associated with it.     
    Service can not be deleted if there are not in CREATED status.      
    Log the service deletion activity with the associated token.
    """,
)
async def delete_service(
    fParam: DeleteForm = Depends(),
    bearer=Depends(bearer_operator),
    request_info=Depends(getters.requestInfo),
):
    try:
        session = sessionMaker()
        token = validators.operatorToken(bearer.credentials, session)
        role = getters.operatorRole(token, session)
        validators.operatorPermission(role, OperatorRole.delete_service)

        service = (
            session.query(Service)
            .filter(Service.id == fParam.id)
            .filter(Service.company_id == token.company_id)
            .first()
        )
        if service and service.status != ServiceStatus.CREATED:
            raise exceptions.DataInUse(Service)
        if service is not None:
            session.delete(service)
            session.commit()
            logEvent(
                token,
                request_info,
                jsonable_encoder(service, exclude={"private_key", "public_key"}),
            )
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    except Exception as e:
        exceptions.handle(e)
    finally:
        session.close()


@route_operator.get(
    "/company/service",
    tags=["Service"],
    response_model=List[ServiceSchema],
    responses=makeExceptionResponses([exceptions.InvalidToken]),
    description="""
    Fetch a list of all services owned by the operator's company.          
    Only available to users with a valid operator token.        
    Supports filtering, sorting, and pagination.
    """,
)
async def fetch_service(
    qParam: QueryParamsForOP = Depends(), bearer=Depends(bearer_operator)
):
    try:
        session = sessionMaker()
        token = validators.operatorToken(bearer.credentials, session)

        qParam = QueryParamsForEX(**qParam.model_dump(), company_id=token.company_id)
        return searchService(session, qParam)
    except Exception as e:
        exceptions.handle(e)
    finally:
        session.close()
