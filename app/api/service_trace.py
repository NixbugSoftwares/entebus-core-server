from datetime import datetime
from enum import IntEnum
from typing import List, Optional
from fastapi import APIRouter, Depends, Query, Form
from sqlalchemy.orm.session import Session
from pydantic import BaseModel, Field
from shapely.geometry import Point
from shapely import wkt, wkb
from sqlalchemy import func
from geoalchemy2 import Geography

from app.api.bearer import bearer_executive, bearer_operator, bearer_vendor
from app.src.db import (
    Route,
    Service,
    Landmark,
    Duty,
    ServiceTrace,
    sessionMaker,
)
from app.src import exceptions, validators, getters
from app.src.loggers import logEvent
from app.src.enums import ServiceStatus, DutyStatus
from app.src.functions import (
    enumStr,
    makeExceptionResponses,
    updateIfChanged,
    promoteToParent,
)
from app.src.urls import URL_SERVICE_TRACE

route_executive = APIRouter()
route_vendor = APIRouter()
route_operator = APIRouter()


## Output Schema
class ServiceTraceSchema(BaseModel):
    id: int
    company_id: int
    duty_id: Optional[int]
    service_id: int
    landmark_id: int
    location: Optional[str]
    accurate: Optional[float]
    updated_on: Optional[datetime]
    created_on: datetime


## Input Forms
class UpdateForm(BaseModel):
    id: int = Field(Form())
    landmark_id: int | None = Field(Form(default=None))
    duty_id: int | None = Field(Form(default=None))
    location: str | None = Field(Form(default=None))
    accurate: float | None = Field(Form(default=None))


## Query Params
class OrderIn(IntEnum):
    ASC = 1
    DESC = 2


class OrderBy(IntEnum):
    id = 1
    location = 2
    updated_on = 3
    created_on = 4


class QueryParamsForOP(BaseModel):
    # Filters
    landmark_id: int | None = Field(Query(default=None))
    duty_id: int | None = Field(Query(default=None))
    service_id: int | None = Field(Query(default=None))
    location: str | None = Field(
        Query(default=None, description="Accepts only SRID 4326 (WGS84)")
    )
    # id based
    id: int | None = Field(Query(default=None))
    id_ge: int | None = Field(Query(default=None))
    id_le: int | None = Field(Query(default=None))
    id_list: List[int] | None = Field(Query(default=None))
    # accurate based
    accurate_ge: float | None = Field(Query(default=None))
    accurate_le: float | None = Field(Query(default=None))
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


def searchServiceTrace(
    session: Session, qParam: QueryParamsForOP | QueryParamsForEX | QueryParamsForVE
) -> List[ServiceTrace]:
    query = session.query(ServiceTrace)

    # Pre-processing
    if qParam.location is not None:
        geometry = validators.WKTstring(qParam.location, Point)
        validators.SRID4326(geometry)
        qParam.location = wkt.dumps(geometry)
    # Filters
    if qParam.landmark_id is not None:
        query = query.filter(ServiceTrace.landmark_id == qParam.landmark_id)
    if qParam.duty_id is not None:
        query = query.filter(ServiceTrace.duty_id == qParam.duty_id)
    if qParam.service_id is not None:
        query = query.filter(ServiceTrace.service_id == qParam.service_id)
    if qParam.company_id is not None:
        query = query.filter(ServiceTrace.company_id == qParam.company_id)
    # id based
    if qParam.id is not None:
        query = query.filter(ServiceTrace.id == qParam.id)
    if qParam.id_ge is not None:
        query = query.filter(ServiceTrace.id >= qParam.id_ge)
    if qParam.id_le is not None:
        query = query.filter(ServiceTrace.id <= qParam.id_le)
    if qParam.id_list is not None:
        query = query.filter(ServiceTrace.id.in_(qParam.id_list))
    # accurate based
    if qParam.accurate_ge is not None:
        query = query.filter(ServiceTrace.accurate >= qParam.accurate_ge)
    if qParam.accurate_ge is not None:
        query = query.filter(ServiceTrace.accurate <= qParam.accurate_le)
    # updated_on based
    if qParam.updated_on_ge is not None:
        query = query.filter(ServiceTrace.updated_on >= qParam.updated_on_ge)
    if qParam.updated_on_le is not None:
        query = query.filter(ServiceTrace.updated_on <= qParam.updated_on_le)
    # created_on based
    if qParam.created_on_ge is not None:
        query = query.filter(ServiceTrace.created_on >= qParam.created_on_ge)
    if qParam.created_on_le is not None:
        query = query.filter(ServiceTrace.created_on <= qParam.created_on_le)

    # Ordering
    if qParam.order_by == OrderBy.location:
        if qParam.location is not None:
            orderingAttribute = func.ST_Distance(
                ServiceTrace.location.cast(Geography),
                func.ST_GeogFromText(qParam.location),
            )
        else:
            orderingAttribute = ServiceTrace.location
    else:
        orderingAttribute = getattr(ServiceTrace, OrderBy(qParam.order_by).name)
    if qParam.order_in == OrderIn.ASC:
        query = query.order_by(orderingAttribute.asc())
    else:
        query = query.order_by(orderingAttribute.desc())

    # Pagination
    query = query.offset(qParam.offset).limit(qParam.limit)
    serviceTraces = query.all()

    # Post-processing
    for serviceTrace in serviceTraces:
        if serviceTrace.location is not None:
            serviceTrace.location = (wkb.loads(bytes(serviceTrace.location.data))).wkt
        else:
            serviceTrace.location = None
    return serviceTraces


## API endpoints [Executive]
@route_executive.get(
    URL_SERVICE_TRACE,
    tags=["Service Trace"],
    response_model=List[ServiceTraceSchema],
    responses=makeExceptionResponses(
        [
            exceptions.InvalidToken,
            exceptions.InvalidWKTStringOrType,
            exceptions.InvalidSRID4326,
        ]
    ),
    description="""
    Retrieve a list of service trace with advanced filtering, sorting, and pagination.  
    Supports spatial queries using a reference location in SRID 4326, and ordering by proximity or metadata fields.  
    Only accessible to authenticated executives.
    """,
)
async def fetch_service_trace(
    qParam: QueryParamsForEX = Depends(), bearer=Depends(bearer_executive)
):
    try:
        session = sessionMaker()
        validators.executiveToken(bearer.credentials, session)

        return searchServiceTrace(session, qParam)
    except Exception as e:
        exceptions.handle(e)
    finally:
        session.close()


## API endpoints [Vendor]
@route_vendor.get(
    URL_SERVICE_TRACE,
    tags=["Service Trace"],
    response_model=List[ServiceTraceSchema],
    responses=makeExceptionResponses(
        [
            exceptions.InvalidToken,
            exceptions.InvalidWKTStringOrType,
            exceptions.InvalidSRID4326,
        ]
    ),
    description="""
    Retrieve a list of service trace with filtering and sorting options available to vendor accounts.  
    Supports spatial filters like proximity to a point, and constraints on metadata fields such as creation date or type.
    """,
)
async def fetch_service_trace(
    qParam: QueryParamsForVE = Depends(), bearer=Depends(bearer_vendor)
):
    try:
        session = sessionMaker()
        validators.vendorToken(bearer.credentials, session)

        return searchServiceTrace(session, qParam)
    except Exception as e:
        exceptions.handle(e)
    finally:
        session.close()


## API endpoints [Operator]
@route_operator.get(
    URL_SERVICE_TRACE,
    tags=["Service Trace"],
    response_model=List[ServiceTraceSchema],
    responses=makeExceptionResponses(
        [
            exceptions.InvalidToken,
            exceptions.InvalidWKTStringOrType,
            exceptions.InvalidSRID4326,
        ]
    ),
    description="""
    Retrieve a list of service trace available to operators.  
    Supports spatial and metadata-based querying with optional sorting and pagination features.
    """,
)
async def fetch_landmark(
    qParam: QueryParamsForOP = Depends(), bearer=Depends(bearer_operator)
):
    try:
        session = sessionMaker()
        token = validators.operatorToken(bearer.credentials, session)

        qParam = promoteToParent(qParam, QueryParamsForEX, company_id=token.company_id)
        return searchServiceTrace(session, qParam)
    except Exception as e:
        exceptions.handle(e)
    finally:
        session.close()
