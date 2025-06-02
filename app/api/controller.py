from fastapi import FastAPI

from app.api.token_management import executive as TM_executive
from app.api.token_management import vendor as TM_vendor
from app.api.token_management import operator as TM_operator

app_executive = FastAPI()
app_vendor = FastAPI()
app_operator = FastAPI()

app_executive.include_router(TM_executive.route_executive)
app_operator.include_router(TM_operator.route_operator)
app_executive.include_router(TM_operator.route_executive)
app_vendor.include_router(TM_vendor.route_vendor)
app_executive.include_router(TM_vendor.route_executive)
