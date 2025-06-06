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
    OperatorToken,
    OperatorRole,
    OperatorRoleMap,
    VendorToken,
    VendorRole,
    VendorRoleMap,
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


def logOperatorEvent(token: OperatorToken, request: dict, data: dict):
    logDetails = {
        "_method": request["method"],
        "_path": request["path"],
        "_operator_id": token.operator_id,
        "_app": "Operator",
    }
    logDetails.update(data)
    openobserve.logEvent(logDetails)


def getOperatorToken(access_token: str, session: Session) -> OperatorToken | None:
    current_time = datetime.now(timezone.utc)
    return (
        session.query(OperatorToken)
        .filter(
            OperatorToken.access_token == access_token,
            OperatorToken.expires_at > current_time,
        )
        .first()
    )


def getOperatorRole(token: OperatorToken, session: Session) -> OperatorRole | None:
    return (
        session.query(OperatorRole)
        .join(OperatorRoleMap, OperatorRole.id == OperatorRoleMap.role_id)
        .filter(OperatorRoleMap.operator_id == token.operator_id)
        .first()
    )


def checkOperatorPermission(role: OperatorRole, permission: Column) -> bool:
    if role and getattr(role, permission.name, False):
        return True
    else:
        return False


def getVendorToken(access_token: str, session: Session) -> VendorToken | None:
    current_time = datetime.now(timezone.utc)
    return (
        session.query(VendorToken)
        .filter(
            VendorToken.access_token == access_token,
            VendorToken.expires_at > current_time,
        )
        .first()
    )


def getVendorRole(token: VendorToken, session: Session) -> VendorRole | None:
    return (
        session.query(VendorRole)
        .join(VendorRoleMap, VendorRole.id == VendorRoleMap.role_id)
        .filter(VendorRoleMap.vendor_id == token.vendor_id)
        .first()
    )


def checkVendorPermission(role: VendorRole, permission: Column) -> bool:
    if role and getattr(role, permission.name, False):
        return True
    else:
        return False


def logVendorEvent(token: VendorToken, request: dict, data: dict):
    logDetails = {
        "_method": request["method"],
        "_path": request["path"],
        "_vendor_id": token.vendor_id,
        "_app": "Vendor",
    }
    logDetails.update(data)
    openobserve.logEvent(logDetails)
