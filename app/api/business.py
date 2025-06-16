from typing import Annotated, Optional
from fastapi import APIRouter, Depends, Form, status
from fastapi.encoders import jsonable_encoder
from pydantic_extra_types.phone_numbers import PhoneNumber
from pydantic import EmailStr
from shapely.geometry import Point

from app.api.bearer import bearer_executive
from app.src import schemas, exceptions
from app.src.db import sessionMaker, Business
from app.src.enums import BusinessStatus, BusinessType
from app.src.functions import (
    enumStr,
    getExecutiveRole,
    getExecutiveToken,
    getRequestInfo,
    isSRID4326,
    logExecutiveEvent,
    makeExceptionResponses,
    toWKTgeometry,
)

route_executive = APIRouter()


@route_executive.post(
    "/business",
    tags=["Business"],
    response_model=schemas.Business,
    status_code=status.HTTP_201_CREATED,
    responses=makeExceptionResponses(
        [
            exceptions.InvalidToken,
            exceptions.NoPermission,
            exceptions.InvalidWKTStringOrType,
            exceptions.InvalidSRID4326,
        ]
    ),
    description="""
    Creates a new business with geospatial point location using SRID 4326 (WGS84).

    - Accepts a WKT **POINT** representing the business's location.
    - Validates geometry format and SRID compliance (must be 4326).
    - Requires executives to have `create_business` permission.
    - Ensures business **phone number** and **email** are unique.
    - Logs the business creation event tied to the authenticated executive.
    """,
)
async def create_business(
    name: Annotated[str, Form(min_length=4, max_length=32)],
    address: Annotated[str, Form(min_length=4, max_length=512)],
    location: Annotated[str, Form(description="WKT POINT with SRID 4326")],
    contact_person: Annotated[str, Form(min_length=4, max_length=64)],
    phone_number: Annotated[PhoneNumber, Form()],
    email_id: Annotated[EmailStr, Form()],
    website: Annotated[Optional[str], Form()] = None,
    status: Annotated[
        BusinessStatus, Form(description=enumStr(BusinessStatus))
    ] = BusinessStatus.ACTIVE,
    type: Annotated[
        BusinessType, Form(description=enumStr(BusinessType))
    ] = BusinessType.OTHER,
    bearer=Depends(bearer_executive),
    request_info=Depends(getRequestInfo),
):
    try:
        session = sessionMaker()
        token = getExecutiveToken(bearer.credentials, session)
        if token is None:
            raise exceptions.InvalidToken()
        role = getExecutiveRole(token, session)
        if not role or not role.create_business:
            raise exceptions.NoPermission()

        wktLocation = toWKTgeometry(location, Point)
        if wktLocation is None:
            raise exceptions.InvalidWKTStringOrType()
        if not isSRID4326(wktLocation):
            raise exceptions.InvalidSRID4326()

        business = Business(
            name=name,
            address=address,
            location=location,
            contact_person=contact_person,
            phone_number=phone_number,
            email_id=email_id,
            website=website,
            status=status,
            type=type,
        )
        session.add(business)
        session.commit()
        logExecutiveEvent(token, request_info, jsonable_encoder(business))
        return business
    except Exception as e:
        exceptions.handle(e)
    finally:
        session.close()
