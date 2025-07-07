from datetime import datetime, date, timedelta
from enum import IntEnum
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, Query, Response, status, Form
from sqlalchemy.orm.session import Session
from fastapi.encoders import jsonable_encoder
from pydantic import BaseModel, Field

from app.api.bearer import bearer_executive, bearer_operator
from app.src.db import (
    Company,
    ExecutiveRole,
    OperatorRole,
    Service,
    Duty,
    sessionMaker,
)
from app.src.constants import TMZ_PRIMARY, TMZ_SECONDARY, SERVICE_START_BUFFER_TIME
from app.src import exceptions, validators, getters
from app.src.loggers import logEvent
from app.src.enums import DutyStatus
from app.src.functions import enumStr, makeExceptionResponses

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
    starting_at: datetime
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
    service_id: int | None = Field(Form(default=None))
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
    company_id: int | None = Field(Query(default=None))
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
def updateDuty(duty: Duty, fParam: UpdateForm):
    dutyStatusTransition = {
        DutyStatus.ASSIGNED: [],
        DutyStatus.STARTED: [DutyStatus.TERMINATED, DutyStatus.ENDED],
        DutyStatus.TERMINATED: [DutyStatus.STARTED],
        DutyStatus.ENDED: [DutyStatus.STARTED],
    }
    if fParam.service_id is not None and fParam.service_id != duty.service_id:
        duty.service_id = fParam.service_id
    if fParam.status is not None and fParam.status != duty.status:
        duty.status = fParam.status
        validators.stateTransition(
            dutyStatusTransition, duty.status, fParam.status, Duty.status
        )


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
    "/company/service/duty",
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
        ]
    ),
    description="""
    Create a new duty for a specified company.                  
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

    except Exception as e:
        exceptions.handle(e)
    finally:
        session.close()


@route_executive.patch(
    "/company/service/duty",
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
    The status=AUDITED and STARTED is not accepted by user input.   
    Log the duty update activity with the associated token.      

    Allowed status transitions:
        STARTED ↔ TERMINATED
        STARTED ↔ ENDED
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

        updateDuty(duty, fParam)
        haveUpdates = session.is_modified(duty)
        if haveUpdates:
            session.commit()
            session.refresh(duty)

        dutyData = jsonable_encoder(duty)
        if haveUpdates:
            logEvent(token, request_info, dutyData)
        return duty
    except Exception as e:
        exceptions.handle(e)
    finally:
        session.close()


@route_executive.delete(
    "/company/service/duty",
    tags=["Duty"],
    status_code=status.HTTP_204_NO_CONTENT,
    responses=makeExceptionResponses(
        [exceptions.InvalidToken, exceptions.NoPermission]
    ),
    description="""
    Delete an existing duty by ID.  
    Requires executive permissions with `delete_duty` role.  
    Deletes the duty and logs the deletion event.
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
        if duty is not None:
            session.delete(duty)
            session.commit()
            logEvent(token, request_info, jsonable_encoder(duty))
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    except Exception as e:
        exceptions.handle(e)
    finally:
        session.close()


@route_executive.get(
    "/company/service/duty",
    tags=["Duty"],
    response_model=list[DutySchema],
    responses=makeExceptionResponses(
        [exceptions.InvalidToken, exceptions.NoPermission]
    ),
    description="""
    Get all duties for a duty.   
    """,
)
async def get_duties(
    qParam: QueryParamsForEX = Depends(),
    bearer=Depends(bearer_executive),
    request_info=Depends(getters.requestInfo),
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
    "/company/service/duty",
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
        ]
    ),
    description="""
    Create a new duty for a specified company.                  
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

    except Exception as e:
        exceptions.handle(e)
    finally:
        session.close()


@route_operator.patch(
    "/company/service/duty",
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
    Requires operator role with `update_duty` permission.       
    The status=AUDITED and STARTED is not accepted by user input.   
    Log the duty update activity with the associated token.      

    Allowed status transitions:
        STARTED ↔ TERMINATED
        STARTED ↔ ENDED
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

        updateDuty(duty, fParam)
        haveUpdates = session.is_modified(duty)
        if haveUpdates:
            session.commit()
            session.refresh(duty)

        dutyData = jsonable_encoder(duty)
        if haveUpdates:
            logEvent(token, request_info, dutyData)
        return duty
    except Exception as e:
        exceptions.handle(e)
    finally:
        session.close()


@route_operator.delete(
    "/company/service/duty",
    tags=["Duty"],
    status_code=status.HTTP_204_NO_CONTENT,
    responses=makeExceptionResponses(
        [exceptions.InvalidToken, exceptions.NoPermission]
    ),
    description="""
    Delete an existing duty by ID.  
    Requires operator permissions with `delete_duty` role.  
    Deletes the duty and logs the deletion event.
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
        if duty is not None:
            session.delete(duty)
            session.commit()
            logEvent(token, request_info, jsonable_encoder(duty))
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    except Exception as e:
        exceptions.handle(e)
    finally:
        session.close()


@route_operator.get(
    "/company/service/duty",
    tags=["Duty"],
    response_model=list[DutySchema],
    responses=makeExceptionResponses(
        [exceptions.InvalidToken, exceptions.NoPermission]
    ),
    description="""
    Get all duties for a duty.   
    """,
)
async def get_duties(
    qParam: QueryParamsForOP = Depends(),
    bearer=Depends(bearer_operator),
    request_info=Depends(getters.requestInfo),
):
    try:
        session = sessionMaker()
        token = validators.operatorToken(bearer.credentials, session)

        qParam = QueryParamsForEX(**qParam.model_dump(), company_id=token.company_id)
        return searchDuty(session, qParam)
    except Exception as e:
        exceptions.handle(e)
    finally:
        session.close()
