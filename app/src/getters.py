from fastapi import Request
from sqlalchemy.orm.session import Session
from sqlalchemy.orm import DeclarativeMeta

from app.src import schemas
from app.src.db import (
    ExecutiveRole,
    ExecutiveRoleMap,
    ExecutiveToken,
    OperatorRole,
    OperatorRoleMap,
    OperatorToken,
    VendorRole,
    VendorRoleMap,
    VendorToken,
)


def requestInfo(request: Request) -> schemas.RequestInfo:
    """
    Extract metadata about the incoming request.

    Args:
        request (Request): FastAPI request object.

    Returns:
        schemas.RequestInfo: Pydantic model containing:
            - method (str): HTTP method (GET, POST, etc.).
            - path (str): Path portion of the request URL.
            - app_id (int): Application ID from app state.
    """
    return schemas.RequestInfo(
        method=request.method,
        path=request.url.path,
        app_id=request.scope["app"].state.id,
    )


def _getRole(
    session: Session,
    role_cls: DeclarativeMeta,
    role_map_cls: DeclarativeMeta,
    foreign_key: str,
    token: object,
) -> object | None:
    """
    Generic role-fetching utility.

    Args:
        session (Session): Active SQLAlchemy session.
        role_cls: Role model class (e.g., ExecutiveRole).
        role_map_cls: Role mapping model class (e.g., ExecutiveRoleMap).
        foreign_key (str): Attribute name in role_map_cls pointing to the account ID.
        token: Token object (ExecutiveToken, OperatorToken, or VendorToken).

    Returns:
        object | None: Role instance if found, else None.
    """
    account_id = getattr(token, foreign_key)
    return (
        session.query(role_cls)
        .join(role_map_cls, role_cls.id == role_map_cls.role_id)
        .filter(getattr(role_map_cls, foreign_key) == account_id)
        .first()
    )


def executiveRole(token: ExecutiveToken, session: Session) -> ExecutiveRole | None:
    """Fetch the role associated with an executive token."""
    return _getRole(
        session,
        ExecutiveRole,
        ExecutiveRoleMap,
        ExecutiveRoleMap.executive_id.name,
        token,
    )


def operatorRole(token: OperatorToken, session: Session) -> OperatorRole | None:
    """Fetch the role associated with an operator token."""
    return _getRole(
        session, OperatorRole, OperatorRoleMap, OperatorRoleMap.operator_id.name, token
    )


def vendorRole(token: VendorToken, session: Session) -> VendorRole | None:
    """Fetch the role associated with a vendor token."""
    return _getRole(
        session, VendorRole, VendorRoleMap, VendorRoleMap.vendor_id.name, token
    )
