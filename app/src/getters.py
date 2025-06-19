from sqlalchemy.orm.session import Session

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


def executiveRole(token: ExecutiveToken, session: Session) -> ExecutiveRole | None:
    return (
        session.query(ExecutiveRole)
        .join(ExecutiveRoleMap, ExecutiveRole.id == ExecutiveRoleMap.role_id)
        .filter(ExecutiveRoleMap.executive_id == token.executive_id)
        .first()
    )


def operatorRole(token: OperatorToken, session: Session) -> OperatorRole | None:
    return (
        session.query(OperatorRole)
        .join(OperatorRoleMap, OperatorRole.id == OperatorRoleMap.role_id)
        .filter(OperatorRoleMap.operator_id == token.operator_id)
        .first()
    )


def vendorRole(token: VendorToken, session: Session) -> VendorRole | None:
    return (
        session.query(VendorRole)
        .join(VendorRoleMap, VendorRole.id == VendorRoleMap.role_id)
        .filter(VendorRoleMap.vendor_id == token.vendor_id)
        .first()
    )
