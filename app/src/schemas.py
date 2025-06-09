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
