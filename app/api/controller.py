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
    route,
    bus,
    landmark_in_route,
    vendor_account,
    schedule,
    service,
    fare,
    duty,
    executive_role,
    executive_role_map,
    operator_role,
    operator_role_map,
    vendor_role,
    vendor_role_map,
    paper_ticket,
    executive_picture,
    service_trace,
)
from app.src.enums import AppID


# ------------------------------------------------------
# Create separate FastAPI apps for each user domain
# ------------------------------------------------------
app_executive = FastAPI(title="Executive APP")
app_vendor = FastAPI(title="Vendor APP")
app_operator = FastAPI(title="Operator APP")
app_public = FastAPI(title="Public APP")

# Tag each app with its AppID
app_executive.state.id = AppID.EXECUTIVE
app_vendor.state.id = AppID.VENDOR
app_operator.state.id = AppID.OPERATOR
app_public.state.id = AppID.PUBLIC


# ------------------------------------------------------
# Executive routers
# ------------------------------------------------------
app_executive.include_router(executive_token.route_executive)
app_executive.include_router(executive_account.route_executive)
app_executive.include_router(executive_role.route_executive)
app_executive.include_router(executive_role_map.route_executive)
app_executive.include_router(executive_picture.route_executive)

# Shared domain routers (landmarks, bus stops, etc.)
app_executive.include_router(landmark.route_executive)
app_executive.include_router(bus_stop.route_executive)
app_executive.include_router(company.route_executive)
app_executive.include_router(operator_token.route_executive)
app_executive.include_router(operator_account.route_executive)
app_executive.include_router(operator_role.route_executive)
app_executive.include_router(operator_role_map.route_executive)
app_executive.include_router(bus.route_executive)
app_executive.include_router(fare.route_executive)
app_executive.include_router(route.route_executive)
app_executive.include_router(landmark_in_route.route_executive)
app_executive.include_router(schedule.route_executive)
app_executive.include_router(service.route_executive)
app_executive.include_router(duty.route_executive)
app_executive.include_router(paper_ticket.route_executive)
app_executive.include_router(service_trace.route_executive)
app_executive.include_router(business.route_executive)
app_executive.include_router(vendor_token.route_executive)
app_executive.include_router(vendor_account.route_executive)
app_executive.include_router(vendor_role.route_executive)
app_executive.include_router(vendor_role_map.route_executive)


# ------------------------------------------------------
# Operator routers
# ------------------------------------------------------
app_operator.include_router(landmark.route_operator)
app_operator.include_router(bus_stop.route_operator)
app_operator.include_router(company.route_operator)
app_operator.include_router(operator_token.route_operator)
app_operator.include_router(operator_account.route_operator)
app_operator.include_router(operator_role.route_operator)
app_operator.include_router(operator_role_map.route_operator)
app_operator.include_router(bus.route_operator)
app_operator.include_router(fare.route_operator)
app_operator.include_router(route.route_operator)
app_operator.include_router(landmark_in_route.route_operator)
app_operator.include_router(schedule.route_operator)
app_operator.include_router(service.route_operator)
app_operator.include_router(duty.route_operator)
app_operator.include_router(paper_ticket.route_operator)
app_operator.include_router(service_trace.route_operator)


# ------------------------------------------------------
# Vendor routers
# ------------------------------------------------------
app_vendor.include_router(landmark.route_vendor)
app_vendor.include_router(bus_stop.route_vendor)
app_vendor.include_router(company.route_vendor)
app_vendor.include_router(bus.route_vendor)
app_vendor.include_router(fare.route_vendor)
app_vendor.include_router(route.route_vendor)
app_vendor.include_router(landmark_in_route.route_vendor)
app_vendor.include_router(service.route_vendor)
app_vendor.include_router(service_trace.route_vendor)
app_vendor.include_router(business.route_vendor)
app_vendor.include_router(vendor_token.route_vendor)
app_vendor.include_router(vendor_account.route_vendor)
app_vendor.include_router(vendor_role.route_vendor)
app_vendor.include_router(vendor_role_map.route_vendor)


# ------------------------------------------------------
# Public routers
# ------------------------------------------------------
app_public.include_router(company.route_public)
app_public.include_router(business.route_public)
