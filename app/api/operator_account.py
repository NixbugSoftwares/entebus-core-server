from fastapi import (
    APIRouter,
    Depends,
    status,
    Form,
)
from fastapi.encoders import jsonable_encoder
from pydantic import BaseModel, Field
from pydantic_extra_types.phone_numbers import PhoneNumber
from pydantic import EmailStr

from app.api.bearer import bearer_executive, bearer_operator
from app.src.enums import GenderType
from app.src import argon2, exceptions, schemas
from app.src.constants import REGEX_USERNAME, REGEX_PASSWORD
from app.src.db import (
    sessionMaker,
    Operator,
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


class CreateFormForOperator(BaseModel):
    username: str = Field(Form(pattern=REGEX_USERNAME, min_length=4, max_length=32))
    password: str = Field(Form(pattern=REGEX_PASSWORD, min_length=8, max_length=32))
    gender: GenderType = Field(
        Form(description=enumStr(GenderType), default=GenderType.OTHER)
    )
    full_name: str | None = Field(Form(max_length=32, default=None))
    email_id: EmailStr | None = Field(Form(max_length=256, default=None))
    phone_number: PhoneNumber | None = Field(Form(max_length=32, default=None))


class CreateFormForExecutive(CreateFormForOperator):
    company_id: int = Field(Form())


## API endpoints [Operator]
@route_operator.post(
    "/company/account",
    tags=["Account"],
    response_model=schemas.Operator,
    status_code=status.HTTP_201_CREATED,
    responses=makeExceptionResponses(
        [
            exceptions.InvalidToken,
            exceptions.NoPermission,
        ]
    ),
    description="""
    Creates a new operator account with an active status.

    - Only operator with `create_operator` permission can create operator.
    - Logs the operator account creation activity with the associated token.
    - Follow patterns for smooth creation of username and password.
    - Phone number must follow RFC3966 format.
    - Email ID must follow RFC5322 format.
    """,
)
async def create_operator(
    fParam: CreateFormForOperator = Depends(),
    bearer=Depends(bearer_operator),
    request_info=Depends(getRequestInfo),
):
    try:
        session = sessionMaker()
        token = getOperatorToken(bearer.credentials, session)
        if token is None:
            raise exceptions.InvalidToken()
        role = getOperatorRole(token, session)
        canCreateOperator = bool(role and role.create_operator)
        if not canCreateOperator:
            raise exceptions.NoPermission()

        password = argon2.makePassword(fParam.password)
        operator = Operator(
            company_id=token.company_id,
            username=fParam.username,
            password=password,
            gender=fParam.gender,
            full_name=fParam.full_name,
            phone_number=fParam.phone_number,
            email_id=fParam.email_id,
        )
        session.add(operator)
        session.commit()
        logOperatorEvent(
            token,
            request_info,
            jsonable_encoder(operator, exclude={"password"}),
        )
        session.expunge(operator)
        return operator
    except Exception as e:
        exceptions.handle(e)
    finally:
        session.close()


## API endpoints [Executive]
@route_executive.post(
    "/company/account",
    tags=["Operator Account"],
    response_model=schemas.Operator,
    status_code=status.HTTP_201_CREATED,
    responses=makeExceptionResponses(
        [
            exceptions.InvalidToken,
            exceptions.NoPermission,
        ]
    ),
    description="""
    Creates a new operator account with an active status.

    - Only executive with `create_operator` permission can create operator.
    - Logs the executive account creation activity with the associated token.
    - Follow patterns for smooth creation of username and password.
    - Phone number must follow RFC3966 format.
    - Email ID must follow RFC5322 format.
    """,
)
async def create_operator(
    fParam: CreateFormForExecutive = Depends(),
    bearer=Depends(bearer_executive),
    request_info=Depends(getRequestInfo),
):
    try:
        session = sessionMaker()
        token = getExecutiveToken(bearer.credentials, session)
        if token is None:
            raise exceptions.InvalidToken()
        role = getExecutiveRole(token, session)
        canCreateOperator = bool(role and role.create_operator)
        if not canCreateOperator:
            raise exceptions.NoPermission()

        password = argon2.makePassword(fParam.password)
        operator = Operator(
            company_id=fParam.company_id,
            username=fParam.username,
            password=password,
            gender=fParam.gender,
            full_name=fParam.full_name,
            phone_number=fParam.phone_number,
            email_id=fParam.email_id,
        )
        session.add(operator)
        session.commit()
        logExecutiveEvent(
            token,
            request_info,
            jsonable_encoder(operator, exclude={"password"}),
        )
        session.expunge(operator)
        return operator
    except Exception as e:
        exceptions.handle(e)
    finally:
        session.close()
