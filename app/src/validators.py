from datetime import datetime, timezone
from sqlalchemy.orm.session import Session
from sqlalchemy import Column

from app.src.db import (
    ExecutiveRole,
    ExecutiveToken,
    OperatorRole,
    OperatorToken,
    VendorRole,
    VendorToken,
)
from app.src import exceptions


# Validate token (raise exceptions.InvalidToken())
def executiveToken(access_token: str, session: Session) -> ExecutiveToken:
    current_time = datetime.now(timezone.utc)
    token = (
        session.query(ExecutiveToken)
        .filter(
            ExecutiveToken.access_token == access_token,
            ExecutiveToken.expires_at > current_time,
        )
        .first()
    )
    if token is None:
        raise exceptions.InvalidToken()
    return token


def vendorToken(access_token: str, session: Session) -> VendorToken:
    current_time = datetime.now(timezone.utc)
    token = (
        session.query(VendorToken)
        .filter(
            VendorToken.access_token == access_token,
            VendorToken.expires_at > current_time,
        )
        .first()
    )
    if token is None:
        raise exceptions.InvalidToken()
    return token


def operatorToken(access_token: str, session: Session) -> OperatorToken:
    current_time = datetime.now(timezone.utc)
    token = (
        session.query(OperatorToken)
        .filter(
            OperatorToken.access_token == access_token,
            OperatorToken.expires_at > current_time,
        )
        .first()
    )
    if token is None:
        raise exceptions.InvalidToken()
    return token


# Validate permission (raise exceptions.NoPermission())
def executivePermission(role: ExecutiveRole, permission: Column) -> bool:
    if role and getattr(role, permission.name, False):
        return True
    else:
        raise exceptions.NoPermission()


def vendorPermission(role: VendorRole, permission: Column) -> bool:
    if role and getattr(role, permission.name, False):
        return True
    else:
        raise exceptions.NoPermission()


def operatorPermission(role: OperatorRole, permission: Column) -> bool:
    if role and getattr(role, permission.name, False):
        return True
    else:
        raise exceptions.NoPermission()
