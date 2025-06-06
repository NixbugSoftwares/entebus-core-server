from typing import Any, List
from fastapi import Request
from sqlalchemy.orm.session import Session
from sqlalchemy import Column
from datetime import timezone, datetime
from sqlalchemy.orm.session import Session
from sqlalchemy import Column
from datetime import timezone, datetime

from app.src import openobserve, schemas
from app.src.db import (
    ExecutiveToken,
    ExecutiveRole,
    ExecutiveRoleMap,
)
from app.src.db import (
    ExecutiveToken,
    ExecutiveRole,
    ExecutiveRoleMap,
)


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


def enumStr(enumClass):
    return ", ".join(f"{x.name}: {x.value}" for x in enumClass)


def getExecutiveToken(access_token: str, session: Session) -> ExecutiveToken | None:
    current_time = datetime.now(timezone.utc)
    return (
        session.query(ExecutiveToken)
        .filter(
            ExecutiveToken.access_token == access_token,
            ExecutiveToken.expires_at > current_time,
        )
        .first()
    )


def getExecutiveRole(token: ExecutiveToken, session: Session) -> ExecutiveRole | None:
    return (
        session.query(ExecutiveRole)
        .join(ExecutiveRoleMap, ExecutiveRole.id == ExecutiveRoleMap.role_id)
        .filter(ExecutiveRoleMap.executive_id == token.executive_id)
        .first()
    )


def checkExecutivePermission(role: ExecutiveRole, permission: Column) -> bool:
    if role and getattr(role, permission.name, False):
        return True
    else:
        return False
