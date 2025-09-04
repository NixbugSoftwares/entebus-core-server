"""
API Endpoint URL Constants

This module defines the URL paths used throughout the application
for accessing different resources in the transport system.

These URLs are relative paths and are typically prefixed by the API
gateway or service base URL when making requests.
"""

# -------------------------------
# Authentication & Tokens
# -------------------------------
URL_OPERATOR_TOKEN = "/company/account/token"
URL_EXECUTIVE_TOKEN = "/entebus/account/token"
URL_VENDOR_TOKEN = "/business/account/token"

# -------------------------------
# Account
# -------------------------------
URL_EXECUTIVE_ACCOUNT = "/entebus/account"
URL_EXECUTIVE_PICTURE = "/entebus/account/picture"

URL_OPERATOR_ACCOUNT = "/company/account"
URL_OPERATOR_PICTURE = "/company/account/picture"

URL_VENDOR_ACCOUNT = "/business/account"
URL_OPERATOR_PICTURE = "/business/account/picture"

# -------------------------------
# Roles & Role Mappings
# -------------------------------
URL_EXECUTIVE_ROLE = "/entebus/role"
URL_EXECUTIVE_ROLE_MAP = "/entebus/account/role"

URL_OPERATOR_ROLE = "/company/role"
URL_OPERATOR_ROLE_MAP = "/company/account/role"

URL_VENDOR_ROLE = "/business/role"
URL_VENDOR_ROLE_MAP = "/business/account/role"

# -------------------------------
# Common Entities
# -------------------------------
URL_LANDMARK = "/landmark"
URL_BUS_STOP = "/landmark/bus_stop"

# -------------------------------
# Company
# -------------------------------
URL_COMPANY = "/company"
URL_ROUTE = "/company/route"
URL_LANDMARK_IN_ROUTE = "/company/route/landmark"
URL_BUS = "/company/bus"
URL_FARE = "/company/fare"
URL_SCHEDULE = "/company/schedule"
URL_SCHEDULE_TRIGGER = "/company/schedule/trigger"
URL_SERVICE = "/company/service"
URL_DUTY = "/company/service/duty"
URL_PAPER_TICKET = "/company/service/ticket/paper"
URL_SERVICE_TRACE = "/company/service/location"

# -------------------------------
# Business
# -------------------------------
URL_BUSINESS = "/business"
