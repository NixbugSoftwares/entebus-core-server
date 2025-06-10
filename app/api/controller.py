from fastapi import FastAPI

from app.api import executive_token
from app.api import operator_token
from app.api import vendor_token
from app.api import landmark, busStop

app_executive = FastAPI()
app_vendor = FastAPI()
app_operator = FastAPI()

app_executive.include_router(executive_token.route_executive)
app_operator.include_router(operator_token.route_operator)
app_executive.include_router(operator_token.route_executive)
app_vendor.include_router(vendor_token.route_vendor)
app_executive.include_router(vendor_token.route_executive)

app_executive.include_router(landmark.route_executive)
app_operator.include_router(landmark.route_operator)
app_vendor.include_router(landmark.route_vendor)

app_executive.include_router(busStop.route_executive)