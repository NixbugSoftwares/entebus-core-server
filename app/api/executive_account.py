from datetime import datetime
from enum import IntEnum
from typing import List, Optional
from fastapi import APIRouter, Depends, Query, Response, status, Form
from fastapi.encoders import jsonable_encoder
from pydantic import BaseModel, Field, EmailStr
from pydantic_extra_types.phone_numbers import PhoneNumber

from app.api.bearer import bearer_executive
from app.src.constants import REGEX_PASSWORD, REGEX_USERNAME
from app.src.db import Executive, ExecutiveRole, ExecutiveToken, sessionMaker
from app.src import argon2, exceptions, validators, getters
from app.src.enums import AccountStatus, GenderType
from app.src.loggers import logEvent
from app.src.functions import enumStr, makeExceptionResponses

route_executive = APIRouter()


## Output Schema
class ExecutiveSchema(BaseModel):
    id: int
    username: str
    gender: int
    full_name: Optional[str]
    designation: Optional[str]
    phone_number: Optional[str]
    email_id: Optional[str]
    status: int
    updated_on: Optional[datetime]
    created_on: datetime


class CreateForm(BaseModel):
    username: str = Field(Form(pattern=REGEX_USERNAME, min_length=4, max_length=32))
    password: str = Field(Form(pattern=REGEX_PASSWORD, min_length=8, max_length=32))
    gender: GenderType = Field(
        Form(description=enumStr(GenderType), default=GenderType.OTHER)
    )
    full_name: str | None = Field(Form(max_length=32, default=None))
    designation: str | None = Field(Form(max_length=32, default=None))
    phone_number: PhoneNumber | None = Field(
        Form(max_length=32, default=None, description="Phone number in RFC3966 format")
    )
    email_id: EmailStr | None = Field(
        Form(max_length=256, default=None, description="Email in RFC 5322 format")
    )


class UpdateForm(BaseModel):
    id: int | None = Field(Form(default=None))
    password: str | None = Field(
        Form(pattern=REGEX_PASSWORD, min_length=8, max_length=32, default=None)
    )
    gender: GenderType | None = Field(
        Form(description=enumStr(GenderType), default=None)
    )
    full_name: str | None = Field(Form(max_length=32, default=None))
    designation: str | None = Field(Form(max_length=32, default=None))
    phone_number: PhoneNumber | None = Field(
        Form(max_length=32, default=None, description="Phone number in RFC3966 format")
    )
    email_id: EmailStr | None = Field(
        Form(max_length=256, default=None, description="Email in RFC 5322 format")
    )
    status: AccountStatus | None = Field(
        Form(description=enumStr(AccountStatus), default=None)
    )


class DeleteForm(BaseModel):
    id: int = Field(Form())


## Query Parameters
class OrderIn(IntEnum):
    ASC = 1
    DESC = 2


class OrderBy(IntEnum):
    id = 1
    updated_on = 2
    created_on = 3


class QueryParams(BaseModel):
    username: str | None = Field(Query(default=None))
    gender: GenderType | None = Field(
        Query(default=None, description=enumStr(GenderType))
    )
    full_name: str | None = Field(Query(default=None))
    designation: str | None = Field(Query(default=None))
    phone_number: str | None = Field(Query(default=None))
    email_id: str | None = Field(Query(default=None))
    status: AccountStatus | None = Field(
        Query(default=None, description=enumStr(AccountStatus))
    )
    # id based
    id: int | None = Field(Query(default=None))
    id_ge: int | None = Field(Query(default=None))
    id_le: int | None = Field(Query(default=None))
    id_list: List[int] | None = Field(Query(default=None))
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


## API endpoints [Executive]
@route_executive.post(
    "/entebus/account",
    tags=["Account"],
    response_model=ExecutiveSchema,
    status_code=status.HTTP_201_CREATED,
    responses=makeExceptionResponses(
        [exceptions.InvalidToken, exceptions.NoPermission]
    ),
    description="""
    Create a new executive account.     
    Only authorized users with `create_executive` permission can create a new executive.    
    The password is hashed using Argon2 before storing.     
    Duplicate usernames are not allowed.
    """,
)
async def create_executive(
    fParam: CreateForm = Depends(),
    bearer=Depends(bearer_executive),
    request_info=Depends(getters.requestInfo),
):
    try:
        session = sessionMaker()
        token = validators.executiveToken(bearer.credentials, session)
        role = getters.executiveRole(token, session)
        validators.executivePermission(role, ExecutiveRole.create_executive)

        fParam.password = argon2.makePassword(fParam.password)
        executive = Executive(
            username=fParam.username,
            password=fParam.password,
            gender=fParam.gender,
            full_name=fParam.full_name,
            designation=fParam.designation,
            phone_number=fParam.phone_number,
            email_id=fParam.email_id,
        )
        session.add(executive)
        session.commit()
        session.refresh(executive)

        executiveData = jsonable_encoder(executive, exclude={"password"})
        logEvent(token, request_info, executiveData)
        return executiveData
    except Exception as e:
        exceptions.handle(e)
    finally:
        session.close()


@route_executive.patch(
    "/entebus/account",
    tags=["Account"],
    response_model=ExecutiveSchema,
    responses=makeExceptionResponses(
        [exceptions.InvalidToken, exceptions.NoPermission, exceptions.InvalidIdentifier]
    ),
    description="""
    Update an existing executive account.   
    Executives can update their own account but cannot update their own status.     
    Authorized users with `update_executive` permission can update any executive.   
    Password changes are securely hashed.   
    Modifications are only saved if changes are detected.
    """,
)
async def update_executive(
    fParam: UpdateForm = Depends(),
    bearer=Depends(bearer_executive),
    request_info=Depends(getters.requestInfo),
):
    try:
        session = sessionMaker()
        token = validators.executiveToken(bearer.credentials, session)
        role = getters.executiveRole(token, session)

        if fParam.id is None:
            fParam.id = token.executive_id
        isSelfUpdate = fParam.id == token.executive_id
        hasUpdatePermission = bool(role and role.update_executive)
        if not isSelfUpdate and not hasUpdatePermission:
            raise exceptions.NoPermission()

        executive = session.query(Executive).filter(Executive.id == fParam.id).first()
        if executive is None:
            raise exceptions.InvalidIdentifier()

        if fParam.password is not None:
            executive.password = argon2.makePassword(fParam.password)
        if fParam.gender is not None and executive.gender != fParam.gender:
            executive.gender = fParam.gender
        if fParam.full_name is not None and executive.full_name != fParam.full_name:
            executive.full_name = fParam.full_name
        if (
            fParam.designation is not None
            and executive.designation != fParam.designation
        ):
            executive.designation = fParam.designation
        if (
            fParam.phone_number is not None
            and executive.phone_number != fParam.phone_number
        ):
            executive.phone_number = fParam.phone_number
        if fParam.email_id is not None and executive.email_id != fParam.email_id:
            executive.email_id = fParam.email_id
        if fParam.status is not None and executive.status != fParam.status:
            if isSelfUpdate or not hasUpdatePermission:
                raise exceptions.NoPermission()
            # Remove all the tokens
            if fParam.status == AccountStatus.SUSPENDED:
                session.query(ExecutiveToken).filter(
                    ExecutiveToken.executive_id == fParam.id
                ).delete()
            executive.status = fParam.status

        haveUpdates = session.is_modified(executive)
        if haveUpdates:
            session.commit()
            session.refresh(executive)

        executiveData = jsonable_encoder(executive, exclude={"password"})
        if haveUpdates:
            logEvent(token, request_info, executiveData)
        return executiveData
    except Exception as e:
        exceptions.handle(e)
    finally:
        session.close()


@route_executive.delete(
    "/entebus/account",
    tags=["Account"],
    status_code=status.HTTP_204_NO_CONTENT,
    responses=makeExceptionResponses(
        [exceptions.InvalidToken, exceptions.NoPermission]
    ),
    description="""
    Delete an executive account.    
    Only users with the `delete_executive` permission can delete executive accounts.    
    Self-deletion is not allowed for safety reasons.    
    If the specified executive exists, it will be deleted permanently.  
    The deleted account details are logged for audit purposes.
    """,
)
async def delete_executive(
    fParam: DeleteForm = Depends(),
    bearer=Depends(bearer_executive),
    request_info=Depends(getters.requestInfo),
):
    try:
        session = sessionMaker()
        token = validators.executiveToken(bearer.credentials, session)
        role = getters.executiveRole(token, session)
        validators.executivePermission(role, ExecutiveRole.delete_executive)

        # Prevent self deletion
        if fParam.id == token.executive_id:
            raise exceptions.NoPermission()

        executive = session.query(Executive).filter(Executive.id == fParam.id).first()
        if executive is not None:
            session.delete(executive)
            session.commit()
            logEvent(
                token, request_info, jsonable_encoder(executive, exclude={"password"})
            )
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    except Exception as e:
        exceptions.handle(e)
    finally:
        session.close()


@route_executive.get(
    "/entebus/account",
    tags=["Account"],
    response_model=List[ExecutiveSchema],
    responses=makeExceptionResponses([exceptions.InvalidToken]),
    description="""
    Fetch executive accounts with filtering, sorting, and pagination.   
    Filter by username, gender, designation, contact details, status, and creation/update timestamps.   
    Filter by ID ranges or lists.   
    Sort by ID, creation date, or update date in ascending or descending order. 
    Paginate using offset and limit.    
    Returns a list of executive accounts matching the criteria.
    """,
)
async def fetch_executive(
    qParam: QueryParams = Depends(), bearer=Depends(bearer_executive)
):
    try:
        session = sessionMaker()
        validators.executiveToken(bearer.credentials, session)

        query = session.query(Executive)

        # Filters
        if qParam.username is not None:
            query = query.filter(Executive.username.ilike(f"%{qParam.username}%"))
        if qParam.gender is not None:
            query = query.filter(Executive.gender == qParam.gender)
        if qParam.full_name is not None:
            query = query.filter(Executive.full_name.ilike(f"%{qParam.full_name}%"))
        if qParam.designation is not None:
            query = query.filter(Executive.designation.ilike(f"%{qParam.designation}%"))
        if qParam.phone_number is not None:
            query = query.filter(
                Executive.phone_number.ilike(f"%{qParam.phone_number}%")
            )
        if qParam.email_id is not None:
            query = query.filter(Executive.email_id.ilike(f"%{qParam.email_id}%"))
        if qParam.status is not None:
            query = query.filter(Executive.status == qParam.status)
        # id based
        if qParam.id is not None:
            query = query.filter(Executive.id == qParam.id)
        if qParam.id_ge is not None:
            query = query.filter(Executive.id >= qParam.id_ge)
        if qParam.id_le is not None:
            query = query.filter(Executive.id <= qParam.id_le)
        if qParam.id_list is not None:
            query = query.filter(Executive.id.in_(qParam.id_list))
        # updated_on based
        if qParam.updated_on_ge is not None:
            query = query.filter(Executive.updated_on >= qParam.updated_on_ge)
        if qParam.updated_on_le is not None:
            query = query.filter(Executive.updated_on <= qParam.updated_on_le)
        # created_on based
        if qParam.created_on_ge is not None:
            query = query.filter(Executive.created_on >= qParam.created_on_ge)
        if qParam.created_on_le is not None:
            query = query.filter(Executive.created_on <= qParam.created_on_le)

        # Ordering
        orderingAttribute = getattr(Executive, OrderBy(qParam.order_by).name)
        if qParam.order_in == OrderIn.ASC:
            query = query.order_by(orderingAttribute.asc())
        else:
            query = query.order_by(orderingAttribute.desc())

        # Pagination
        query = query.offset(qParam.offset).limit(qParam.limit)
        return query.all()
    except Exception as e:
        exceptions.handle(e)
    finally:
        session.close()
