from datetime import datetime, time
from enum import IntEnum
from typing import List, Optional
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
from app.src.db import ExecutiveRole, OperatorRole, sessionMaker, Route
from app.src import exceptions, validators, getters
from app.src.loggers import logEvent
from app.src.functions import enumStr, makeExceptionResponses

route_executive = APIRouter()
route_vendor = APIRouter()
route_operator = APIRouter()


## Output Schema
class LandmarkInRoute(BaseModel):
    id: int
    company_id: int
    route_id: int
    landmark_id: int
    distance_from_start: int
    arrival_delta: int
    departure_delta: int
    updated_on: Optional[datetime]
    created_on: datetime


## Input Forms
class CreateForm(BaseModel):
    route_id: int = Field(Form())
    landmark_id: time = Field(Form())
    distance_from_start: int = Field(Form(gt=-1))
    arrival_delta: int = Field(Form(gt=-1))
    departure_delta: int = Field(Form(gt=-1))


class UpdateForm(BaseModel):
    id: int = Field(Form())
    distance_from_start: int | None = Field(Form(gt=-1, default=None))
    arrival_delta: int | None = Field(Form(gt=-1, default=None))
    departure_delta: int | None = Field(Form(gt=-1, default=None))


class DeleteForm(BaseModel):
    id: int = Field(Form())


## Query Parameters
class OrderIn(IntEnum):
    ASC = 1
    DESC = 2


class OrderBy(IntEnum):
    id = 1
    distance_from_start: 2
    updated_on = 3
    created_on = 4


class QueryParamsForOP(BaseModel):
    route_id: int | None = Field(Query(default=None))
    landmark_id: int | None = Field(Query(default=None))
    # id based
    id: int | None = Field(Query(default=None))
    id_ge: int | None = Field(Query(default=None))
    id_le: int | None = Field(Query(default=None))
    id_list: List[int] | None = Field(Query(default=None))
    # distance_from_start based
    distance_from_start_ge: int | None = Field(Query(default=None))
    distance_from_start_le: int | None = Field(Query(default=None))
    # arrival_delta based
    arrival_delta_ge: int | None = Field(Query(default=None))
    arrival_delta_le: int | None = Field(Query(default=None))
    # departure_delta based
    departure_delta_ge: int | None = Field(Query(default=None))
    departure_delta_le: int | None = Field(Query(default=None))
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


class QueryParams(QueryParamsForOP):
    company_id: int | None = Field(Query(default=None))


## Function
def updateLandmarkInRoute(landmark: LandmarkInRoute, fParam: UpdateForm):
    if (
        fParam.distance_from_start is not None
        and landmark.distance_from_start != fParam.distance_from_start
    ):
        landmark.distance_from_start = fParam.distance_from_start
    if (
        fParam.arrival_delta is not None
        and landmark.arrival_delta != fParam.arrival_delta
    ):
        landmark.arrival_delta = fParam.arrival_delta
    if (
        fParam.departure_delta is not None
        and landmark.departure_delta != fParam.departure_delta
    ):
        landmark.departure_delta = fParam.departure_delta


def searchLandmarkInRoute(
    session: Session, qParam: QueryParams | QueryParamsForOP
) -> List[LandmarkInRoute]:
    query = session.query(LandmarkInRoute)

    # Filters
    if qParam.company_id is not None:
        query = query.filter(LandmarkInRoute.company_id == qParam.company_id)
    if qParam.route_id is not None:
        query = query.filter(LandmarkInRoute.route_id == qParam.route_id)
    if qParam.landmark_id is not None:
        query = query.filter(LandmarkInRoute.landmark_id == qParam.landmark_id)
    # id based
    if qParam.id is not None:
        query = query.filter(LandmarkInRoute.id == qParam.id)
    if qParam.id_ge is not None:
        query = query.filter(LandmarkInRoute.id >= qParam.id_ge)
    if qParam.id_le is not None:
        query = query.filter(LandmarkInRoute.id <= qParam.id_le)
    if qParam.id_list is not None:
        query = query.filter(LandmarkInRoute.id.in_(qParam.id_list))
    # distance_from_start based
    if qParam.distance_from_start_ge is not None:
        query = query.filter(
            LandmarkInRoute.distance_from_start >= qParam.distance_from_start_ge
        )
    if qParam.distance_from_start_le is not None:
        query = query.filter(
            LandmarkInRoute.distance_from_start <= qParam.distance_from_start_le
        )
    # arrival_delta based
    if qParam.arrival_delta_ge is not None:
        query = query.filter(LandmarkInRoute.arrival_delta >= qParam.arrival_delta_ge)
    if qParam.arrival_delta_le is not None:
        query = query.filter(LandmarkInRoute.arrival_delta <= qParam.arrival_delta_le)
    # departure_delta based
    if qParam.departure_delta_ge is not None:
        query = query.filter(
            LandmarkInRoute.departure_delta >= qParam.departure_delta_ge
        )
    if qParam.departure_delta_le is not None:
        query = query.filter(
            LandmarkInRoute.departure_delta <= qParam.departure_delta_le
        )
    # updated_on based
    if qParam.updated_on_ge is not None:
        query = query.filter(LandmarkInRoute.updated_on >= qParam.updated_on_ge)
    if qParam.updated_on_le is not None:
        query = query.filter(LandmarkInRoute.updated_on <= qParam.updated_on_le)
    # created_on based
    if qParam.created_on_ge is not None:
        query = query.filter(LandmarkInRoute.created_on >= qParam.created_on_ge)
    if qParam.created_on_le is not None:
        query = query.filter(LandmarkInRoute.created_on <= qParam.created_on_le)

    # Ordering
    orderingAttribute = getattr(LandmarkInRoute, OrderBy(qParam.order_by).name)
    if qParam.order_in == OrderIn.ASC:
        query = query.order_by(orderingAttribute.asc())
    else:
        query = query.order_by(orderingAttribute.desc())

    # Pagination
    query = query.offset(qParam.offset).limit(qParam.limit)
    return query.all()
