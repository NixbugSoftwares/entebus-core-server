from datetime import datetime, timedelta, timezone
from enum import IntEnum
from typing import List, Optional
from fastapi import APIRouter, Depends, Query, Response, status, Form
from sqlalchemy.orm.session import Session
from fastapi.encoders import jsonable_encoder
from pydantic import BaseModel, Field

from app.api.bearer import bearer_executive, bearer_operator
from app.src.db import (
    Company,
    Operator,
    ExecutiveRole,
    OperatorRole,
    Service,
    Duty,
    sessionMaker,
)
from app.src.constants import SERVICE_START_BUFFER_TIME
from app.src import exceptions, validators, getters
from app.src.loggers import logEvent
from app.src.enums import DutyStatus, ServiceStatus, AccountStatus
from app.src.functions import enumStr, makeExceptionResponses, promoteToParent
from app.src.urls import URL_DUTY

route_executive = APIRouter()
route_vendor = APIRouter()
route_operator = APIRouter()


## Output Schema
class DutySchema(BaseModel):
    id: int
    company_id: int
    operator_id: int
    service_id: int
    status: int
    started_on: Optional[datetime]
    finished_on: Optional[datetime]
    updated_on: Optional[datetime]
    created_on: datetime


## Input Forms
class CreateFormForOP(BaseModel):
    service_id: int = Field(Form())
    operator_id: int = Field(Form())


class CreateFormForEX(CreateFormForOP):
    company_id: int = Field(Form())


class UpdateForm(BaseModel):
    id: int = Field(Form())
    status: DutyStatus | None = Field(
        Form(description=enumStr(DutyStatus), default=None)
    )


class DeleteForm(BaseModel):
    id: int = Field(Form())


## Query Params
class OrderIn(IntEnum):
    ASC = 1
    DESC = 2


class OrderBy(IntEnum):
    id = 1
    started_on = 2
    finished_on = 3
    updated_on = 4
    created_on = 5


class QueryParamsForOP(BaseModel):
    # Filters
    operator_id: int | None = Field(Query(default=None))
    service_id: int | None = Field(Query(default=None))
    status: DutyStatus | None = Field(
        Query(default=None, description=enumStr(DutyStatus))
    )
    # id based
    id: int | None = Field(Query(default=None))
    id_ge: int | None = Field(Query(default=None))
    id_le: int | None = Field(Query(default=None))
    id_list: List[int] | None = Field(Query(default=None))
    # started_on based
    started_on_ge: datetime | None = Field(Query(default=None))
    started_on_le: datetime | None = Field(Query(default=None))
    # finished_on based
    finished_on_ge: datetime | None = Field(Query(default=None))
    finished_on_le: datetime | None = Field(Query(default=None))
    # status based
    status: DutyStatus | None = Field(
        Query(default=None, description=enumStr(DutyStatus))
    )
    status_list: List[DutyStatus] | None = Field(
        Query(default=None, description=enumStr(DutyStatus))
    )
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
def updateDuty(session: Session, duty: Duty, fParam: UpdateForm):
    dutyStatusTransition = {
        DutyStatus.ASSIGNED: [DutyStatus.STARTED, DutyStatus.NOT_USED],
        DutyStatus.STARTED: [DutyStatus.TERMINATED, DutyStatus.ENDED],
        DutyStatus.TERMINATED: [DutyStatus.STARTED],
        DutyStatus.ENDED: [DutyStatus.STARTED],
        DutyStatus.NOT_USED: [],
    }
    service = session.query(Service).filter(Service.id == duty.service_id).first()
    if fParam.status is not None and fParam.status != duty.status:
        validators.stateTransition(
            dutyStatusTransition, duty.status, fParam.status, Duty.status
        )
        if fParam.status == DutyStatus.STARTED:
            duty.started_on = datetime.now(timezone.utc)
            service.status = ServiceStatus.STARTED
            if service.started_on is None:
                service.started_on = datetime.now(timezone.utc)
        if fParam.status in [DutyStatus.TERMINATED, DutyStatus.ENDED]:
            duty.finished_on = datetime.now(timezone.utc)
        duty.status = fParam.status


def searchDuty(
    session: Session, qParam: QueryParamsForOP | QueryParamsForEX
) -> List[Duty]:
    query = session.query(Duty)

    # Filters
    if qParam.operator_id is not None:
        query = query.filter(Duty.operator_id == qParam.operator_id)
    if qParam.company_id is not None:
        query = query.filter(Duty.company_id == qParam.company_id)
    if qParam.service_id is not None:
        query = query.filter(Duty.service_id == qParam.service_id)
    if qParam.status is not None:
        query = query.filter(Duty.status == qParam.status)
    # id based filters
    if qParam.id is not None:
        query = query.filter(Duty.id == qParam.id)
    if qParam.id_ge is not None:
        query = query.filter(Duty.id >= qParam.id_ge)
    if qParam.id_le is not None:
        query = query.filter(Duty.id <= qParam.id_le)
    if qParam.id_list is not None:
        query = query.filter(Duty.id.in_(qParam.id_list))
    # status based
    if qParam.status is not None:
        query = query.filter(Duty.status == qParam.status)
    if qParam.status_list is not None:
        query = query.filter(Duty.status.in_(qParam.status_list))
    # started_on based filters
    if qParam.started_on_ge is not None:
        query = query.filter(Duty.started_on >= qParam.started_on_ge)
    if qParam.started_on_le is not None:
        query = query.filter(Duty.started_on <= qParam.started_on_le)
    # finished_on-based filters
    if qParam.finished_on_ge is not None:
        query = query.filter(Duty.finished_on >= qParam.finished_on_ge)
    if qParam.finished_on_le is not None:
        query = query.filter(Duty.finished_on <= qParam.finished_on_le)
    # updated_on based filters
    if qParam.updated_on_ge is not None:
        query = query.filter(Duty.updated_on >= qParam.updated_on_ge)
    if qParam.updated_on_le is not None:
        query = query.filter(Duty.updated_on <= qParam.updated_on_le)
    # created_on based filters
    if qParam.created_on_ge is not None:
        query = query.filter(Duty.created_on >= qParam.created_on_ge)
    if qParam.created_on_le is not None:
        query = query.filter(Duty.created_on <= qParam.created_on_le)

    # Ordering
    orderingAttribute = getattr(Duty, OrderBy(qParam.order_by).name)
    if qParam.order_in == OrderIn.ASC:
        query = query.order_by(orderingAttribute.asc())
    else:
        query = query.order_by(orderingAttribute.desc())

    # Pagination
    query = query.offset(qParam.offset).limit(qParam.limit)
    return query.all()


## API endpoints [Executive]
@route_executive.post(
    URL_DUTY,
    tags=["Duty"],
    response_model=DutySchema,
    status_code=status.HTTP_201_CREATED,
    responses=makeExceptionResponses(
        [
            exceptions.InvalidToken,
            exceptions.NoPermission,
            exceptions.UnknownValue(Duty.service_id),
            exceptions.InvalidAssociation(Duty.operator_id, Duty.company_id),
            exceptions.InactiveResource(Service),
            exceptions.DuplicateDuty(Duty.operator_id, Duty.service_id),
        ]
    ),
    description="""
    Create a new duty for a specified company.      
    Requires executive role with `create_duty` permission.      
    Duty can not be created if the service is not in CREATED or STARTED status. 
    In this operator and service must be associated with the company_id.    
    The operator must be in active status.  
    The duty is created in the Assigned status by default.      
    Assigning multiple duties to the same operator under the same service is restricted.    
    Log the duty creation activity with the associated token.
    """,
)
async def create_duty(
    fParam: CreateFormForEX = Depends(),
    bearer=Depends(bearer_executive),
    request_info=Depends(getters.requestInfo),
):
    try:
        session = sessionMaker()
        token = validators.executiveToken(bearer.credentials, session)
        role = getters.executiveRole(token, session)
        validators.executivePermission(role, ExecutiveRole.create_duty)

        company = session.query(Company).filter(Company.id == fParam.company_id).first()
        if company is None:
            raise exceptions.UnknownValue(Duty.company_id)
        operator = (
            session.query(Operator).filter(Operator.id == fParam.operator_id).first()
        )
        if operator is None:
            raise exceptions.UnknownValue(Duty.operator_id)
        service = session.query(Service).filter(Service.id == fParam.service_id).first()
        if service is None:
            raise exceptions.UnknownValue(Duty.service_id)

        if operator.status != AccountStatus.ACTIVE:
            raise exceptions.InactiveResource(Operator)
        if service.status not in [ServiceStatus.CREATED, ServiceStatus.STARTED]:
            raise exceptions.InactiveResource(Service)

        if operator.company_id != company.id:
            raise exceptions.InvalidAssociation(Duty.operator_id, Duty.company_id)
        if service.company_id != company.id:
            raise exceptions.InvalidAssociation(Duty.operator_id, Duty.company_id)

        duties = (
            session.query(Duty)
            .filter(Duty.operator_id == fParam.operator_id)
            .filter(Duty.service_id == fParam.service_id)
            .filter(Duty.status == DutyStatus.ASSIGNED)
            .first()
        )
        if duties is not None:
            raise exceptions.DuplicateDuty(Duty.operator_id, Duty.service_id)

        duty = Duty(
            company_id=fParam.company_id,
            operator_id=fParam.operator_id,
            service_id=fParam.service_id,
        )
        session.add(duty)
        session.commit()
        session.refresh(duty)

        dutyData = jsonable_encoder(duty)
        logEvent(token, request_info, dutyData)
        return dutyData
    except Exception as e:
        exceptions.handle(e)
    finally:
        session.close()


@route_executive.patch(
    URL_DUTY,
    tags=["Duty"],
    response_model=DutySchema,
    responses=makeExceptionResponses(
        [
            exceptions.InvalidToken,
            exceptions.NoPermission,
            exceptions.InvalidIdentifier,
            exceptions.InvalidStateTransition("status"),
        ]
    ),
    description="""
    Update an existing duty by ID.      
    Requires executive role with `update_duty` permission.   
    When status is updated to STARTED, the started_on field is set to current time and service status is set to STARTED.    
    When status is updated to TERMINATED or ENDED, the finished_on field is set to current time.    
    Log the duty update activity with the associated token.      

    Allowed status transitions:
        STARTED ↔ TERMINATED
        STARTED ↔ ENDED
        ASSIGNED → STARTED
        ASSIGNED → NOT_USED
    """,
)
async def update_duty(
    fParam: UpdateForm = Depends(),
    bearer=Depends(bearer_executive),
    request_info=Depends(getters.requestInfo),
):
    try:
        session = sessionMaker()
        token = validators.executiveToken(bearer.credentials, session)
        role = getters.executiveRole(token, session)
        validators.executivePermission(role, ExecutiveRole.update_duty)

        duty = session.query(Duty).filter(Duty.id == fParam.id).first()
        if duty is None:
            raise exceptions.InvalidIdentifier()
        if fParam.status in [DutyStatus.STARTED, DutyStatus.ENDED]:
            raise exceptions.NoPermission()

        updateDuty(session, duty, fParam)
        haveUpdates = session.is_modified(duty)
        if haveUpdates:
            session.commit()
            session.refresh(duty)

        dutyData = jsonable_encoder(duty)
        if haveUpdates:
            logEvent(token, request_info, dutyData)
        return dutyData
    except Exception as e:
        exceptions.handle(e)
    finally:
        session.close()


@route_executive.delete(
    URL_DUTY,
    tags=["Duty"],
    status_code=status.HTTP_204_NO_CONTENT,
    responses=makeExceptionResponses(
        [exceptions.InvalidToken, exceptions.NoPermission, exceptions.DataInUse(Duty)]
    ),
    description="""
    Delete an existing duty by ID.   
    Only executive with `delete_duty` permission can perform this operation.   
    Deletes the duty and logs the deletion event.   
    
    Deletion Rules:*    
        STARTED: Deletion is not allowed.    
        ASSIGNED: Deletion is permitted.    
        `ENDED` or `TERMINATED`: Deletion is allowed only if no paper ticket is associated with the record. 
    """,
)
async def delete_duty(
    fParam: DeleteForm = Depends(),
    bearer=Depends(bearer_executive),
    request_info=Depends(getters.requestInfo),
):
    try:
        session = sessionMaker()
        token = validators.executiveToken(bearer.credentials, session)
        role = getters.executiveRole(token, session)
        validators.executivePermission(role, ExecutiveRole.delete_duty)

        duty = session.query(Duty).filter(Duty.id == fParam.id).first()
        if duty is None:
            return Response(status_code=status.HTTP_204_NO_CONTENT)
        if duty.status == DutyStatus.STARTED:
            raise exceptions.DataInUse(Duty)
        session.delete(duty)
        session.commit()
        logEvent(token, request_info, jsonable_encoder(duty))
    except Exception as e:
        exceptions.handle(e)
    finally:
        session.close()


@route_executive.get(
    URL_DUTY,
    tags=["Duty"],
    response_model=list[DutySchema],
    responses=makeExceptionResponses([exceptions.InvalidToken]),
    description="""
    Fetch a list of all duties across companies.     
    Only available to users with a valid executive token.       
    Supports filtering, sorting, and pagination.
    """,
)
async def get_duties(
    qParam: QueryParamsForEX = Depends(), bearer=Depends(bearer_executive)
):
    try:
        session = sessionMaker()
        validators.executiveToken(bearer.credentials, session)

        return searchDuty(session, qParam)
    except Exception as e:
        exceptions.handle(e)
    finally:
        session.close()


## API endpoints [Operator]
@route_operator.post(
    URL_DUTY,
    tags=["Duty"],
    response_model=DutySchema,
    status_code=status.HTTP_201_CREATED,
    responses=makeExceptionResponses(
        [
            exceptions.InvalidToken,
            exceptions.NoPermission,
            exceptions.UnknownValue(Duty.service_id),
            exceptions.InvalidAssociation(Duty.operator_id, Duty.company_id),
            exceptions.InactiveResource(Duty),
            exceptions.DuplicateDuty(Duty.operator_id, Duty.service_id),
        ]
    ),
    description="""
    Create a new duty for the operator's own company.	      
    Requires operator role with `create_duty` permission.    
    The company ID is derived from the token, not user input.  
    In this operator and service must be associated with the company_id.  
    Duty can not be created if the service is not in CREATED or STARTED status.       
    The operator must be in active status.     
    The duty is created in the Assigned status by default.   
    If the logged in operator_id is same as incoming operator_id and current time is after the buffer time then the duty is self assigned.    
    Sets buffer time with SERVICE_START_BUFFER_TIME (in minutes).
    For self assigned duty the status will be set to STARTED by default, not user input.    
    For self assigned duty the started_on will be set to current time, not user input.  
    For self assigned duty the service status will be set to STARTED by default.    
    For self assigned duty the service started_on will be set to current time.      
    For non self assigned duty the status will be set to ASSIGNED by default, not user input .   
    Assigning multiple duties to the same operator under the same service is restricted.    
    Log the duty creation activity with the associated token.
    """,
)
async def create_duty(
    fParam: CreateFormForOP = Depends(),
    bearer=Depends(bearer_operator),
    request_info=Depends(getters.requestInfo),
):
    try:
        session = sessionMaker()
        token = validators.operatorToken(bearer.credentials, session)
        role = getters.operatorRole(token, session)
        validators.operatorPermission(role, OperatorRole.create_duty)

        operator = (
            session.query(Operator)
            .filter(Operator.id == fParam.operator_id)
            .filter(Operator.company_id == token.company_id)
            .first()
        )
        if operator is None:
            raise exceptions.UnknownValue(Operator.id)
        service = (
            session.query(Service)
            .filter(Service.id == fParam.service_id)
            .filter(Service.company_id == token.company_id)
            .first()
        )
        if service is None:
            raise exceptions.UnknownValue(Duty.service_id)

        if operator.status != AccountStatus.ACTIVE:
            raise exceptions.InactiveResource(Operator)
        if service.status not in [ServiceStatus.CREATED, ServiceStatus.STARTED]:
            raise exceptions.InactiveResource(Service)

        duties = (
            session.query(Duty)
            .filter(Duty.operator_id == fParam.operator_id)
            .filter(Duty.service_id == fParam.service_id)
            .filter(Duty.status == DutyStatus.ASSIGNED)
            .first()
        )
        if duties is not None:
            raise exceptions.DuplicateDuty(Duty.operator_id, Duty.service_id)

        bufferTime = service.starting_at - timedelta(seconds=SERVICE_START_BUFFER_TIME)
        currentTime = datetime.now(timezone.utc)
        if fParam.operator_id == token.operator_id and currentTime >= bufferTime:
            status = DutyStatus.STARTED
            started_on = currentTime
            service.status = ServiceStatus.STARTED
            if service.started_on is None:
                service.started_on = started_on
        else:
            status = DutyStatus.ASSIGNED
            started_on = None

        duty = Duty(
            company_id=token.company_id,
            operator_id=fParam.operator_id,
            service_id=fParam.service_id,
            status=status,
            started_on=started_on,
        )
        session.add(duty)
        session.commit()
        session.refresh(duty)

        dutyData = jsonable_encoder(duty)
        logEvent(token, request_info, dutyData)
        return dutyData
    except Exception as e:
        exceptions.handle(e)
    finally:
        session.close()


@route_operator.patch(
    URL_DUTY,
    tags=["Duty"],
    response_model=DutySchema,
    responses=makeExceptionResponses(
        [
            exceptions.InvalidToken,
            exceptions.NoPermission,
            exceptions.InvalidIdentifier,
            exceptions.InvalidStateTransition("status"),
        ]
    ),
    description="""
    Update an existing duty belonging to the operator's company.            
    Requires operator role with `update_duty` permission.       
    When status is updated to STARTED, the duty started_on and service started_on field is set to current time and service status is set to STARTED.    
    When status is updated to TERMINATED or ENDED, the finished_on field is set to current time.    
    Duty assigned operator can only update the status to STARTED or ENDED.  
    Log the duty update activity with the associated token.      

    Allowed status transitions:
        STARTED ↔ TERMINATED
        STARTED ↔ ENDED
        ASSIGNED → STARTED
        ASSIGNED → NOT_USED
    """,
)
async def update_duty(
    fParam: UpdateForm = Depends(),
    bearer=Depends(bearer_operator),
    request_info=Depends(getters.requestInfo),
):
    try:
        session = sessionMaker()
        token = validators.operatorToken(bearer.credentials, session)
        role = getters.operatorRole(token, session)
        validators.operatorPermission(role, OperatorRole.update_duty)

        duty = (
            session.query(Duty)
            .filter(Duty.id == fParam.id)
            .filter(Duty.company_id == token.company_id)
            .first()
        )
        if duty is None:
            raise exceptions.InvalidIdentifier()
        if (
            fParam.status in [DutyStatus.STARTED, DutyStatus.ENDED]
            and token.operator_id != duty.operator_id
        ):
            raise exceptions.NoPermission()

        updateDuty(session, duty, fParam)
        haveUpdates = session.is_modified(duty)
        if haveUpdates:
            session.commit()
            session.refresh(duty)

        dutyData = jsonable_encoder(duty)
        if haveUpdates:
            logEvent(token, request_info, dutyData)
        return dutyData
    except Exception as e:
        exceptions.handle(e)
    finally:
        session.close()


@route_operator.delete(
    URL_DUTY,
    tags=["Duty"],
    status_code=status.HTTP_204_NO_CONTENT,
    responses=makeExceptionResponses(
        [exceptions.InvalidToken, exceptions.NoPermission, exceptions.DataInUse(Duty)]
    ),
    description="""
    Delete an existing duty by ID.    
    Only operator with `delete_duty` permission can perform this operation.   
    Ensures the service is owned by the operator's company. 
    Deletes the duty and logs the deletion event.   

    Deletion Rules: 
        STARTED: Deletion is not allowed.   
        ASSIGNED: Deletion is permitted.    
        `ENDED` or `TERMINATED`: Deletion is allowed only if no paper ticket is associated with the record. 
    """,
)
async def delete_duty(
    fParam: DeleteForm = Depends(),
    bearer=Depends(bearer_operator),
    request_info=Depends(getters.requestInfo),
):
    try:
        session = sessionMaker()
        token = validators.operatorToken(bearer.credentials, session)
        role = getters.operatorRole(token, session)
        validators.operatorPermission(role, OperatorRole.delete_duty)

        duty = (
            session.query(Duty)
            .filter(Duty.id == fParam.id)
            .filter(Duty.company_id == token.company_id)
            .first()
        )
        if duty is None:
            return Response(status_code=status.HTTP_204_NO_CONTENT)
        if duty.status == DutyStatus.STARTED:
            raise exceptions.DataInUse(Duty)
        session.delete(duty)
        session.commit()
        logEvent(token, request_info, jsonable_encoder(duty))
    except Exception as e:
        exceptions.handle(e)
    finally:
        session.close()


@route_operator.get(
    URL_DUTY,
    tags=["Duty"],
    response_model=list[DutySchema],
    responses=makeExceptionResponses([exceptions.InvalidToken]),
    description="""
    Fetch a list of all duties across companies.     
    Only available to users with a valid operator token.       
    Supports filtering, sorting, and pagination.  
    """,
)
async def get_duties(
    qParam: QueryParamsForOP = Depends(), bearer=Depends(bearer_operator)
):
    try:
        session = sessionMaker()
        token = validators.operatorToken(bearer.credentials, session)

        qParam = promoteToParent(qParam, QueryParamsForEX, company_id=token.company_id)
        return searchDuty(session, qParam)
    except Exception as e:
        exceptions.handle(e)
    finally:
        session.close()
