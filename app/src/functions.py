from typing import Any, List
from fastapi import Request

from app.src import openobserve, schemas
from app.src.db import ExecutiveToken


def getRequestInfo(request: Request):
    return {"method": request.method, "path": request.url.path}


def logExecutiveEvent(token: ExecutiveToken, request: dict, data: dict):
    logDetails = {
        "_method": request["method"],
        "_path": request["path"],
        "_executive_id": token.executive_id,
        "_app": "Executive",
    }
    logDetails.update(data)
    openobserve.logEvent(logDetails)


def makeExceptionResponses(exceptions: List[Any]):
    responses = {}
    for exception in exceptions:
        responses[exception.status_code] = {
            "model": schemas.ErrorResponse,
            "description": exception.detail,
            "content": {"application/json": {"example": {"detail": exception.detail}}},
        }
    return responses
