from datetime import datetime
from typing import Optional
from pydantic import BaseModel


class RequestInfo(BaseModel):
    method: str
    path: str
    app_id: int


class HealthStatus(BaseModel):
    status: str
    version: str


class ErrorResponse(BaseModel):
    detail: str


class MaskedVendorToken(BaseModel):
    id: int
    business_id: int
    vendor_id: int
    expires_in: int
    platform_type: int
    client_details: Optional[str]
    created_on: datetime
    updated_on: Optional[datetime]


class VendorToken(MaskedVendorToken):
    access_token: str
    token_type: Optional[str] = "bearer"


class Operator(BaseModel):
    id: int
    company_id: int
    username: str
    gender: int
    full_name: Optional[str]
    phone_number: Optional[str]
    email_id: Optional[str]
    status: int
    updated_on: Optional[datetime]
    created_on: datetime


class Bus(BaseModel):
    id: int
    company_id: int
    registration_number: str
    name: str
    capacity: int
    manufactured_on: datetime
    insurance_upto: Optional[datetime]
    pollution_upto: Optional[datetime]
    fitness_upto: Optional[datetime]
    road_tax_upto: Optional[datetime]
    status: int
    updated_on: Optional[datetime]
    created_on: datetime
