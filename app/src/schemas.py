from datetime import datetime
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
