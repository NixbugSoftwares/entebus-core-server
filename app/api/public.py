from typing import List
from fastapi import APIRouter, Depends
from sqlalchemy.orm.session import Session

from app.src.db import sessionMaker
from app.api import business as business_api
from app.api import company as company_api
from app.src import exceptions

route_public = APIRouter()


@route_public.get(
    "/company",
    tags=["Company"],
    response_model=List[company_api.CompanySchema],
    description="""
    Public endpoint to fetch company list.
    No authentication required.
    """,
)
async def fetch_public_company(qParam: company_api.QueryParamsForEX = Depends()):
    try:
        session = sessionMaker()
        return company_api.searchCompany(session, qParam)
    except Exception as e:
        exceptions.handle(e)
    finally:
        session.close()


@route_public.get(
    "/business",
    tags=["Business"],
    response_model=List[business_api.BusinessSchema],
    description="""
    Public endpoint to fetch business list.
    No authentication required.
    """,
)
async def fetch_public_business(qParam: business_api.QueryParamsForEX = Depends()):
    try:
        session = sessionMaker()
        return business_api.searchBusiness(session, qParam)
    except Exception as e:
        exceptions.handle(e)
    finally:
        session.close()
