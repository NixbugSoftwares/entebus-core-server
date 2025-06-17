from typing import Annotated, List
from fastapi import APIRouter, Depends, Form, status, Query, Response
from fastapi.encoders import jsonable_encoder
from pydantic_extra_types.phone_numbers import PhoneNumber
from pydantic import EmailStr
from enum import IntEnum
from datetime import datetime

from app.api.bearer import bearer_executive
from app.src.enums import GenderType, OrderIn, AccountStatus
from app.src import schemas, exceptions, argon2
from app.src.constants import REGEX_USERNAME, REGEX_PASSWORD
from app.src.db import (
    sessionMaker,
    Executive,
    ExecutiveToken,
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


## Schemas
class OrderBy(IntEnum):
    id = 1
    created_on = 2


## API endpoints [Executive]
@route_executive.post(
    "/entebus/account",
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


@route_executive.get(
    "/entebus/account",
    tags=["Account"],
    response_model=List[schemas.Executive],
    responses=makeExceptionResponses([exceptions.InvalidToken]),
    description="""
    Retrieves a list of executive account filtered by optional query parameters.

    - Any authorized executive can access the endpoint.
    - Supports filtering by executive ID range, ID list, gender list, creation timestamps.
    - Enables pagination using `offset` and `limit`  query parameters.
    - Supports ordering by `id` or `created_on`, in ascending or descending order.
    """,
)
async def fetch_executives(
    id: Annotated[int | None, Query()] = None,
    id_ge: Annotated[int | None, Query()] = None,
    id_le: Annotated[int | None, Query()] = None,
    id_list: Annotated[List[int], Query()] = None,
    username: Annotated[str | None, Query()] = None,
    gender: Annotated[GenderType | None, Query(description=enumStr(GenderType))] = None,
    gender_list: Annotated[
        List[GenderType | None], Query(description=enumStr(GenderType))
    ] = None,
    status: Annotated[AccountStatus | None, Query()] = None,
    full_name: Annotated[str | None, Query()] = None,
    designation: Annotated[str | None, Query()] = None,
    phone_number: Annotated[str | None, Query()] = None,
    email_id: Annotated[str | None, Query()] = None,
    created_on: Annotated[datetime | None, Query()] = None,
    created_on_ge: Annotated[datetime | None, Query()] = None,
    created_on_le: Annotated[datetime | None, Query()] = None,
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(gt=0, le=100)] = 20,
    order_by: Annotated[OrderBy, Query(description=enumStr(OrderBy))] = OrderBy.id,
    order_in: Annotated[OrderIn, Query(description=enumStr(OrderIn))] = OrderIn.DESC,
    bearer=Depends(bearer_executive),
):
    try:
        session = sessionMaker()
        token = getExecutiveToken(bearer.credentials, session)
        if token is None:
            raise exceptions.InvalidToken()

        query = session.query(Executive)
        if id is not None:
            query = query.filter(Executive.id == id)
        if id_ge is not None:
            query = query.filter(Executive.id >= id_ge)
        if id_le is not None:
            query = query.filter(Executive.id <= id_le)
        if id_list is not None:
            query = query.filter(Executive.id.in_(id_list))
        if username is not None:
            query = query.filter(Executive.username.ilike(f"%{username}%"))
        if gender is not None:
            query = query.filter(Executive.gender == gender)
        if gender_list is not None:
            query = query.filter(Executive.gender.in_(gender_list))
        if status is not None:
            query = query.filter(Executive.status == status)
        if full_name is not None:
            query = query.filter(Executive.full_name.ilike(f"%{full_name}%"))
        if designation is not None:
            query = query.filter(Executive.designation.ilike(f"%{designation}%"))
        if phone_number is not None:
            query = query.filter(Executive.phone_number.ilike(f"%{phone_number}%"))
        if email_id is not None:
            query = query.filter(Executive.email_id.ilike(f"%{email_id}%"))
        if created_on is not None:
            query = query.filter(Executive.created_on == created_on)
        if created_on_ge is not None:
            query = query.filter(Executive.created_on >= created_on_ge)
        if created_on_le is not None:
            query = query.filter(Executive.created_on <= created_on_le)

        # Apply ordering
        orderQuery = getattr(Executive, OrderBy(order_by).name)
        if order_in == OrderIn.ASC:
            query = query.order_by(orderQuery.asc())
        else:
            query = query.order_by(orderQuery.desc())

        executives = query.limit(limit).offset(offset).all()
        return executives
    except Exception as e:
        exceptions.handle(e)
    finally:
        session.close()


@route_executive.patch(
    "/entebus/account",
    tags=["Account"],
    response_model=schemas.Executive,
    responses=makeExceptionResponses(
        [
            exceptions.InvalidToken,
            exceptions.NoPermission,
            exceptions.InvalidIdentifier,
        ]
    ),
    description="""
    Updates an existing executive account.

    - Executives can update their own account details.
    - Executives with the `update_executive` permission can update other executives.
    - An executive cannot update their own status.
    - If the status is set to `SUSPENDED`, all tokens associated with that executive are revoked.
    - Logs the update activity along with the associated token details.
    """,
)
async def update_executive(
    id: Annotated[int, Form()],
    password: Annotated[
        str | None, Form(pattern=REGEX_PASSWORD, min_length=8, max_length=32)
    ] = None,
    gender: Annotated[GenderType | None, Form(description=enumStr(GenderType))] = None,
    full_name: Annotated[str | None, Form(max_length=32)] = None,
    designation: Annotated[str | None, Form(max_length=32)] = None,
    phone_number: Annotated[PhoneNumber | None, Form(max_length=32)] = None,
    email_id: Annotated[EmailStr | None, Form(max_length=256)] = None,
    status: Annotated[
        AccountStatus | None, Form(description=enumStr(AccountStatus))
    ] = None,
    bearer=Depends(bearer_executive),
    request_info=Depends(getRequestInfo),
):
    try:
        session = sessionMaker()
        token = getExecutiveToken(bearer.credentials, session)
        if token is None:
            raise exceptions.InvalidToken()
        role = getExecutiveRole(token, session)
        forSelf = False
        if id == token.executive_id:
            forSelf = True
        canUpdateExecutive = bool(role and role.update_executive)
        if not forSelf and not canUpdateExecutive:
            raise exceptions.NoPermission()

        executive = session.query(Executive).filter(Executive.id == id).first()
        if executive is None:
            raise exceptions.InvalidIdentifier()
        if password is not None:
            password = argon2.makePassword(password)
            executive.password = password
        if gender is not None and executive.gender != gender:
            executive.gender = gender
        if full_name is not None and executive.full_name != full_name:
            executive.full_name = full_name
        if designation is not None and executive.designation != designation:
            executive.designation = designation
        if phone_number is not None and executive.phone_number != phone_number:
            executive.phone_number = phone_number
        if email_id is not None and executive.email_id != email_id:
            executive.email_id = email_id
        if status is not None and executive.status != status:
            if forSelf or not canUpdateExecutive:
                raise exceptions.NoPermission()
            if status == AccountStatus.SUSPENDED:
                session.query(ExecutiveToken).filter(
                    ExecutiveToken.executive_id == id
                ).delete()
            executive.status = status
        session.commit()
        session.refresh(executive)
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


@route_executive.delete(
    "/entebus/account",
    tags=["Account"],
    status_code=status.HTTP_204_NO_CONTENT,
    responses=makeExceptionResponses(
        [
            exceptions.InvalidToken,
            exceptions.NoPermission,
        ]
    ),
    description="""
    Deletes executive account.

    - Executives can delete their own account.
    - Executives with the `delete_executive` permission can delete other executives.
    - Logs the deletion activity with the associated token details.
    """,
)
async def delete_executive(
    id: Annotated[int, Form()],
    bearer=Depends(bearer_executive),
    request_info=Depends(getRequestInfo),
):
    try:
        session = sessionMaker()
        token = getExecutiveToken(bearer.credentials, session)
        if token is None:
            raise exceptions.InvalidToken()
        role = getExecutiveRole(token, session)
        canDeleteExecutive = bool(role and role.delete_executive)
        if not canDeleteExecutive:
            raise exceptions.NoPermission()

        executive = session.query(Executive).filter(Executive.id == id).first()
        if executive:
            logData = jsonable_encoder(executive)
            session.delete(executive)
            session.commit()
            logExecutiveEvent(token, request_info, logData)
            return Response(status_code=status.HTTP_204_NO_CONTENT)

    except Exception as e:
        session.rollback()
        exceptions.handle(e)
    finally:
        session.close()
