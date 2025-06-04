from typing import Any, List
from fastapi import Request
from sqlalchemy.orm.session import Session
from sqlalchemy import Column
from datetime import timedelta, timezone, datetime

from app.src import openobserve, schemas
from app.src.db import (
    ExecutiveToken,
    ExecutiveRole,
    ExecutiveRoleMap,
)
from app.src import exceptions


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


def verifyExecutiveToken(access_token: str, session: Session) -> ExecutiveToken:
    token = (
        session.query(ExecutiveToken)
        .filter(ExecutiveToken.access_token == access_token)
        .first()
    )
    if token is None:
        raise exceptions.InvalidToken()
    tokenExpiresOn = token.created_on + timedelta(seconds=token.expires_in)
    currentTime = datetime.now(timezone.utc)
    if tokenExpiresOn < currentTime:
        raise exceptions.InvalidToken()
    return token


def getExecutiveRole(token: ExecutiveToken, session: Session) -> ExecutiveRole:
    map = (
        session.query(ExecutiveRoleMap)
        .filter(ExecutiveRoleMap.executive_id == token.executive_id)
        .first()
    )
    if map is not None:
        return (
            session.query(ExecutiveRole).filter(ExecutiveRole.id == map.role_id).first()
        )
    return None


def checkExecutivePermission(role: ExecutiveRole, permission_name: Column) -> bool:
    if role is None or getattr(role, permission_name.name) is False:
        raise False
    else:
        return True
