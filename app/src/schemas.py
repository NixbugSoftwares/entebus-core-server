from datetime import datetime, time
from typing import Optional
from pydantic import BaseModel


class HealthStatus(BaseModel):
    status: str
    version: str


class ErrorResponse(BaseModel):
    detail: str


class MaskedExecutiveToken(BaseModel):
    id: int
    executive_id: int
    expires_in: int
    platform_type: int
    client_details: Optional[str]
    created_on: datetime
    updated_on: Optional[datetime]


class ExecutiveToken(MaskedExecutiveToken):
    access_token: str
    token_type: Optional[str] = "bearer"


class Landmark(BaseModel):
    id: int
    name: str
    version: int
    boundary: str
    type: str
    updated_on: Optional[datetime]
    created_on: datetime


class BusStop(BaseModel):
    id: int
    name: str
    landmark_id: int
    location: str
    created_on: datetime
    updated_on: Optional[datetime]


class MaskedOperatorToken(BaseModel):
    id: int
    operator_id: int
    company_id: int
    expires_in: int
    platform_type: int
    client_details: Optional[str]
    created_on: datetime
    updated_on: Optional[datetime]


class OperatorToken(MaskedOperatorToken):
    access_token: str
    token_type: Optional[str] = "bearer"


class Executive(BaseModel):
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


class MaskedVendorToken(BaseModel):
    id: int
    business_id: int
    vendor_id: int
    expires_in: int
    platform_type: Optional[str] = None
    client_details: Optional[str] = None
    created_on: datetime
    updated_on: Optional[datetime]


class VendorToken(MaskedVendorToken):
    access_token: str
    token_type: Optional[str] = "bearer"


class Company(BaseModel):
    id: int
    name: str
    address: str
    location: str
    contact_person: str
    phone_number: str
    email_id: Optional[str]
    status: int
    type: int
    created_on: datetime
    updated_on: Optional[datetime]


class Route(BaseModel):
    id:                 int
    company_id:         int
    landmark_id:        int
    name:               str
    status:             int
    starting_time:      time
    updated_on:         datetime
    created_on:         Optional[datetime]