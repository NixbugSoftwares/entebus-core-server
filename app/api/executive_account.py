from typing import Annotated
from fastapi import APIRouter, Depends, Form, status
from fastapi.encoders import jsonable_encoder
from pydantic_extra_types.phone_numbers import PhoneNumber
from pydantic import EmailStr

from app.api.bearer import bearer_executive
from app.src.enums import GenderType
from app.src import schemas, exceptions, argon2
from app.src.constants import REGEX_USERNAME, REGEX_PASSWORD
from app.src.db import (
    sessionMaker,
    Executive,
)
from app.src.functions import (
    enumStr,
    getExecutiveRole,
    getExecutiveToken,
    getRequestInfo,
    logExecutiveEvent,
    makeExceptionResponses,
)

route_executive = APIRouter()


## API endpoints [Executive]
@route_executive.post(
    "/account",
    tags=["Account"],
    response_model=schemas.Executive,
    status_code=status.HTTP_201_CREATED,
    responses=makeExceptionResponses(
        [
            exceptions.InvalidToken,
            exceptions.NoPermission,
        ]
    ),
    description="""
    Creates a new executive account with an active status.

    - Only executives with `create_executive` permission can create executives.
    - Logs the executive account creation activity with the associated token.
    - Follow patterns for smooth creation of username and password.
    - Phone number must follow RFC3966 format.
    - Email ID must follow RFC5322 format.
    """,
)
async def create_executive(
    username: Annotated[str, Form(pattern=REGEX_USERNAME, min_length=4, max_length=32)],
    password: Annotated[str, Form(pattern=REGEX_PASSWORD, min_length=8, max_length=32)],
    gender: Annotated[
        GenderType, Form(description=enumStr(GenderType))
    ] = GenderType.OTHER,
    full_name: Annotated[str | None, Form(max_length=32)] = None,
    designation: Annotated[str | None, Form(max_length=32)] = None,
    phone_number: Annotated[PhoneNumber | None, Form(max_length=32)] = None,
    email_id: Annotated[EmailStr | None, Form(max_length=256)] = None,
    bearer=Depends(bearer_executive),
    request_info=Depends(getRequestInfo),
):
    try:
        session = sessionMaker()
        token = getExecutiveToken(bearer.credentials, session)
        if token is None:
            raise exceptions.InvalidToken()
        role = getExecutiveRole(token, session)
        canCreateExecutive = bool(role and role.create_executive)
        if not canCreateExecutive:
            raise exceptions.NoPermission()

        password = argon2.makePassword(password)
        executive = Executive(
            username=username,
            password=password,
            gender=gender,
            full_name=full_name,
            designation=designation,
            phone_number=phone_number,
            email_id=email_id,
        )
        session.add(executive)
        session.commit()
        logExecutiveEvent(
            token,
            request_info,
            jsonable_encoder(executive, exclude={"password"}),
        )
        return executive
    except Exception as e:
        exceptions.handle(e)
    finally:
        session.close()
