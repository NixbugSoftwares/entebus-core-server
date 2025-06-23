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
