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
