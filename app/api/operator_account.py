from sqlalchemy.orm.session import Session
from fastapi import (
    APIRouter,
    Depends,
    status,
    Form,
)
from typing import Annotated
from fastapi.encoders import jsonable_encoder
from pydantic import BaseModel, Field
from pydantic_extra_types.phone_numbers import PhoneNumber
from pydantic import EmailStr

from app.api.bearer import bearer_executive, bearer_operator
from app.src.enums import AccountStatus, GenderType
from app.src import argon2, exceptions, schemas
from app.src.constants import REGEX_USERNAME, REGEX_PASSWORD
from app.src.db import (
    sessionMaker,
    Operator,
    OperatorToken,
)
from app.src.functions import (
    enumStr,
    getRequestInfo,
    logOperatorEvent,
    makeExceptionResponses,
    getOperatorToken,
    getOperatorRole,
    getExecutiveToken,
    getExecutiveRole,
    logExecutiveEvent,
)

route_operator = APIRouter()
route_executive = APIRouter()


## API endpoints [Operator]
@route_operator.post("/company/account", tags=["Account"])
async def create_operator(bearer=Depends(route_executive)):
    pass


## API endpoints [Executive]
@route_operator.post("/company/account", tags=["Operator Account"])
async def create_operator(bearer=Depends(bearer_operator)):
    pass
