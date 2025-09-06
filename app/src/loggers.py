from typing import Union
from app.src.db import ExecutiveToken, OperatorToken, VendorToken
from app.src import openobserve
from app.src.schemas import RequestInfo
from app.src.enums import AppID


def logEvent(
    token: Union[ExecutiveToken, OperatorToken, VendorToken],
    requestInfo: RequestInfo,
    data: dict,
) -> None:
    """
    Log an event to OpenObserve with request and user context.

    Args:
        token (Union[ExecutiveToken, OperatorToken, VendorToken]): Authenticated user token.
        requestInfo (RequestInfo): Metadata about the current request.
        data (dict): Additional event-specific details to include in the log.

    Notes:
        - Automatically attaches `_app_id`, `_method`, `_path`, and user-specific ID.
        - User-specific key depends on the app:
            - Executive → `_executive_id`
            - Operator  → `_operator_id`
            - Vendor    → `_vendor_id`
    """
    logDetails = {
        "_method": requestInfo.method,
        "_path": requestInfo.path,
        "_app_id": requestInfo.app_id,
    }

    if requestInfo.app_id == AppID.EXECUTIVE and isinstance(token, ExecutiveToken):
        logDetails["_executive_id"] = token.executive_id
    elif requestInfo.app_id == AppID.OPERATOR and isinstance(token, OperatorToken):
        logDetails["_operator_id"] = token.operator_id
    elif requestInfo.app_id == AppID.VENDOR and isinstance(token, VendorToken):
        logDetails["_vendor_id"] = token.vendor_id

    logDetails.update(data)
    openobserve.logEvent(logDetails)


# Convenience wrappers (optional — use only if you want explicit naming in routes)
def logExecutiveEvent(
    token: ExecutiveToken, requestInfo: RequestInfo, data: dict
) -> None:
    """Wrapper around logEvent for executive context."""
    logEvent(token, requestInfo, data)


def logVendorEvent(token: VendorToken, requestInfo: RequestInfo, data: dict) -> None:
    """Wrapper around logEvent for vendor context."""
    logEvent(token, requestInfo, data)


def logOperatorEvent(
    token: OperatorToken, requestInfo: RequestInfo, data: dict
) -> None:
    """Wrapper around logEvent for operator context."""
    logEvent(token, requestInfo, data)
