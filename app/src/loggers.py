from typing import Union
from app.src.db import ExecutiveToken, OperatorToken, VendorToken
from app.src import openobserve
from app.src.schemas import RequestInfo
from app.src.enums import AppID


def logExecutiveEvent(token: ExecutiveToken, requestInfo: RequestInfo, data: dict):
    logDetails = {
        "_method": requestInfo["method"],
        "_path": requestInfo["path"],
        "_executive_id": token.executive_id,
        "_app": "Executive",
    }
    logDetails.update(data)
    openobserve.logEvent(logDetails)


def logVendorEvent(token: VendorToken, requestInfo: RequestInfo, data: dict):
    logDetails = {
        "_method": requestInfo["method"],
        "_path": requestInfo["path"],
        "_vendor_id": token.vendor_id,
        "_app": "Vendor",
    }
    logDetails.update(data)
    openobserve.logEvent(logDetails)


def logOperatorEvent(token: OperatorToken, requestInfo: RequestInfo, data: dict):
    logDetails = {
        "_method": requestInfo["method"],
        "_path": requestInfo["path"],
        "_operator_id": token.operator_id,
        "_app": "Operator",
    }
    logDetails.update(data)
    openobserve.logEvent(logDetails)


def logEvent(
    token: Union[OperatorToken, ExecutiveToken, VendorToken],
    requestInfo: RequestInfo,
    data: dict,
):
    if requestInfo.app_id == AppID.EXECUTIVE and isinstance(token, ExecutiveToken):
        logExecutiveEvent(token, requestInfo, data)
    elif requestInfo.app_id == AppID.OPERATOR and isinstance(token, OperatorToken):
        logOperatorEvent(token, requestInfo, data)
    elif requestInfo.app_id == AppID.VENDOR and isinstance(token, VendorToken):
        logVendorEvent(token, requestInfo, data)
