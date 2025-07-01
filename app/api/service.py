from datetime import datetime, date, timedelta
from enum import IntEnum
from typing import List, Optional, Dict, Any
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
    LandmarkInRoute,
    sessionMaker,
)
from app.src import exceptions, validators, getters
from app.src.loggers import logEvent
from app.src.enums import (
    TicketingMode,
    ServiceStatus,
    FareScope,
    CompanyStatus,
    BusStatus,
)
from app.src.functions import enumStr, makeExceptionResponses
from app.src.digital_ticket import v1
from app.src.constants import SERVICE_START_BUFFER_TIME

route_executive = APIRouter()
route_vendor = APIRouter()
route_operator = APIRouter()


## Output Schema
class ServiceSchema(BaseModel):
    id: int
    company_id: int
    route: Dict[str, Any]
    fare: Dict[str, Any]
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
    started_on: datetime | None = Field(Form(default=None))


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
    started_on: datetime | None = Field(Form(default=None))
    finished_on: datetime | None = Field(Form(default=None))
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
def updateService(service: Service, fParam: UpdateForm):
    serviceStatusTransition = {
        ServiceStatus.CREATED: [ServiceStatus.STARTED, ServiceStatus.TERMINATED],
        ServiceStatus.STARTED: [ServiceStatus.TERMINATED, ServiceStatus.ENDED],
        ServiceStatus.TERMINATED: [ServiceStatus.ENDED, ServiceStatus.AUDITED],
        ServiceStatus.ENDED: [ServiceStatus.AUDITED],
    }
    if fParam.ticket_mode is not None and service.ticket_mode != fParam.ticket_mode:
        service.ticket_mode = fParam.ticket_mode
    if fParam.status is not None and service.status != fParam.status:
        validators.stateTransition(
            serviceStatusTransition, service.status, fParam.status, Service.status
        )
        service.status = fParam.status
    if fParam.started_on is not None and service.started_on != fParam.started_on:
        if fParam.started_on is not None:
            bufferTime = service.starting_at - timedelta(
                seconds=SERVICE_START_BUFFER_TIME
            )
            if fParam.started_on <= bufferTime:
                raise exceptions.InvalidValue(Service.started_on)
        service.started_on = fParam.started_on
    if fParam.finished_on is not None and service.finished_on != fParam.finished_on:
        service.finished_on = fParam.finished_on
    if fParam.remark is not None and service.remark != fParam.remark:
        if service.status not in [ServiceStatus.TERMINATED, ServiceStatus.ENDED]:
            raise exceptions.InvalidValue(Service.remark)
        service.remark = fParam.remark


def searchService(
    session: Session, qParam: QueryParamsForOP | QueryParamsForEX
) -> List[Service]:
    query = session.query(Service)

    # Filters
    if qParam.bus_id is not None:
        query = query.filter(Service.bus_id == qParam.bus_id)
    if qParam.ticket_mode is not None:
        query = query.filter(Service.ticket_mode == qParam.ticket_mode)
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
    # starting_at-based filters
    if qParam.starting_at_ge is not None:
        query = query.filter(Service.starting_at >= qParam.starting_at_ge)
    if qParam.starting_at_le is not None:
        query = query.filter(Service.starting_at <= qParam.starting_at_le)
    # ending_at-based filters
    if qParam.ending_at_ge is not None:
        query = query.filter(Service.ending_at >= qParam.ending_at_ge)
    if qParam.ending_at_le is not None:
        query = query.filter(Service.ending_at <= qParam.ending_at_le)
    # updated_on-based filters
    if qParam.updated_on_ge is not None:
        query = query.filter(Service.updated_on >= qParam.updated_on_ge)
    if qParam.updated_on_le is not None:
        query = query.filter(Service.updated_on <= qParam.updated_on_le)
    # created_on-based filters
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
            exceptions.InactiveAccount,
        ]
    ),
    description="""
    Create a new service for a specified company.           
    Requires executive role with `create_service` permission.        
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

        if company.status != CompanyStatus.VERIFIED:
            raise exceptions.InactiveAccount()
        if bus.status != BusStatus.ACTIVE:
            raise exceptions.InactiveAccount()

        if bus.company_id != company.id:
            raise exceptions.InvalidAssociation(Service.bus_id, Service.company_id)
        if route.company_id != company.id:
            raise exceptions.InvalidAssociation(Service.route, Service.company_id)
        validators.landmarkInRoute(route.id, session)
        if fare.scope != FareScope.GLOBAL:
            if fare.company_id != company.id:
                raise exceptions.InvalidAssociation(Service.fare, Service.company_id)

        if fParam.starting_at < date.today():
            raise exceptions.InvalidValue(Service.starting_at)
        if fParam.starting_at.year > 2050:
            raise exceptions.InvalidValue(Service.starting_at)

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
        ending_at = fParam.starting_at + timedelta(minutes=lastLandmark.arrival_delta)

        if fParam.started_on is not None:
            bufferTime = fParam.starting_at - timedelta(
                seconds=SERVICE_START_BUFFER_TIME
            )
            if fParam.started_on <= bufferTime:
                raise exceptions.InvalidValue(Service.started_on)

        routeData = jsonable_encoder(route)
        for landmark in landmarksInRoute:
            routeData["landmark"] = [jsonable_encoder(landmark)]

        fareData = jsonable_encoder(fare)
        ticketCreator = v1.TicketCreator()
        privateKey = ticketCreator.getPEMprivateKeyString()
        publicKey = ticketCreator.getPEMpublicKeyString()

        service = Service(
            company_id=fParam.company_id,
            bus_id=fParam.bus_id,
            route=routeData,
            fare=fareData,
            starting_at=fParam.starting_at,
            started_on=fParam.started_on,
            ending_at=ending_at,
            private_key=privateKey,
            public_key=publicKey,
        )
        session.add(service)
        session.commit()

        serviceData = jsonable_encoder(service, exclude={"private_key", "public_key"})
        logEvent(token, request_info, serviceData)
        return service
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
            exceptions.InvalidValue(Service.started_on),
        ]
    ),
    description="""
    Update an existing service by ID.      
    Requires executive role with `update_service` permission.   
    Log the service update activity with the associated token.
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

        updateService(session, service, fParam)
        haveUpdates = session.is_modified(service)
        if haveUpdates:
            session.commit()
            session.refresh(service)

        serviceData = jsonable_encoder(service, exclude={"private_key", "public_key"})
        if haveUpdates:
            logEvent(token, request_info, serviceData)
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
        [exceptions.InvalidToken, exceptions.NoPermission]
    ),
    description="""
    Delete an existing service by ID.      
    Requires executive role with `delete_service` permission.      
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
        if service is not None:
            session.delete(service)
            session.commit()
            logEvent(token, request_info, jsonable_encoder(service))
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
    response_model=List[ServiceSchema],
    responses=makeExceptionResponses([exceptions.InvalidToken]),
    description="""
    Fetch a list of all service across companies.  
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
            status=None
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
        ]
    ),
    description="""
    Create a new service for the operator's own company.       
    Requires operator role with `create_service` permission.       
    The company ID is derived from the token, not user input.              
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

        company = session.query(Company).filter(Company.id == token.company_id).first()
        if company.status != CompanyStatus.VERIFIED:
            raise exceptions.InactiveAccount()
        if bus.status != BusStatus.ACTIVE:
            raise exceptions.InactiveAccount()

        if fParam.starting_at < date.today():
            raise exceptions.InvalidValue(Service.starting_at)
        if fParam.starting_at.year > 2050:
            raise exceptions.InvalidValue(Service.starting_at)

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
        ending_at = fParam.starting_at + timedelta(minutes=lastLandmark.arrival_delta)

        if fParam.started_on is not None:
            bufferTime = fParam.starting_at - timedelta(
                seconds=SERVICE_START_BUFFER_TIME
            )
            if fParam.started_on <= bufferTime:
                raise exceptions.InvalidValue(Service.started_on)

        routeData = jsonable_encoder(route)
        for landmark in landmarksInRoute:
            routeData["landmark"] = [jsonable_encoder(landmark)]

        fareData = jsonable_encoder(fare)
        ticketCreator = v1.TicketCreator()
        privateKey = ticketCreator.getPEMprivateKeyString()
        publicKey = ticketCreator.getPEMpublicKeyString()

        service = Service(
            company_id=token.company_id,
            bus_id=fParam.bus_id,
            route=routeData,
            fare=fareData,
            starting_at=fParam.starting_at,
            started_on=fParam.started_on,
            ending_at=ending_at,
            private_key=privateKey,
            public_key=publicKey,
        )
        session.add(service)
        session.commit()

        serviceData = jsonable_encoder(service, exclude={"private_key", "public_key"})
        logEvent(token, request_info, serviceData)
        return service

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
            exceptions.InvalidValue(Service.started_on),
        ]
    ),
    description="""
    Update an existing service belonging to the operator's company.        
    Requires operator role with `update_service` permission.       
    Ensures the service is owned by the operator's company.        
    Log the service updating activity with the associated token.
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

        serviceData = jsonable_encoder(service, exclude={"private_key", "public_key"})
        if haveUpdates:
            logEvent(token, request_info, serviceData)
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
        [exceptions.InvalidToken, exceptions.NoPermission]
    ),
    description="""
    Delete an existing service by ID.          
    Requires operator role with `delete_service` permission.       
    Ensures the service is owned by the operator's company.        
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

        if service is not None:
            session.delete(service)
            session.commit()
            logEvent(token, request_info, jsonable_encoder(service))
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
