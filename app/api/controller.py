from fastapi import FastAPI

from app.api import (
    executive_token,
    company,
    operator_token,
    vendor_token,
    landmark,
    bus_stop,
    executive_account,
    operator_account,
    business,
)


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

app_executive.include_router(bus_stop.route_executive)
app_operator.include_router(bus_stop.route_operator)
app_vendor.include_router(bus_stop.route_vendor)

app_executive.include_router(executive_account.route_executive)

app_executive.include_router(company.route_executive)

app_operator.include_router(operator_account.route_operator)
app_executive.include_router(operator_account.route_executive)

app_executive.include_router(business.route_executive)
app_operator.include_router(company.route_operator)
