from traceback import format_exception
from logging import getLogger
from fastapi import status, HTTPException
from sqlalchemy.exc import IntegrityError, DatabaseError
from psycopg2.errorcodes import UNIQUE_VIOLATION, FOREIGN_KEY_VIOLATION
from pydantic import ValidationError
from app.src.constants import IMMUTABLE_ROW_ERROR


# Function to format DB integrity log error
def formatIntegrityError(e: IntegrityError):
    errorMessage: str = e.orig.diag.message_detail
    errorMessage = errorMessage.translate({ord(i): None for i in '\\"\\.\\(\\)'})
    errorMessage = errorMessage.replace("Key ", "For ")
    errorMessage = errorMessage.replace("=", " value ")
    return errorMessage


# Function to log error
def logException(e: Exception):
    detail = str(format_exception(type(e), e, e.__traceback__))
    logger = getLogger("uvicorn.error")
    logger.error(detail)


# Base class for all app specific exceptions
class APIException(HTTPException):
    status_code = status.HTTP_400_BAD_REQUEST
    detail = None
    headers = None

    def __init__(self, *args, **kwargs):
        if "status_code" not in kwargs:
            kwargs["status_code"] = self.status_code
        if "detail" not in kwargs:
            kwargs["detail"] = self.detail
        if "headers" not in kwargs:
            kwargs["headers"] = self.headers
        super().__init__(*args, **kwargs)


# Function to handle exceptions
def handle(e: Exception):
    if isinstance(e, IntegrityError):
        if e.orig.diag.sqlstate == UNIQUE_VIOLATION:
            raise UniqueViolation(formatIntegrityError(e))
        if e.orig.diag.sqlstate == FOREIGN_KEY_VIOLATION:
            raise ForeignKeyViolation(formatIntegrityError(e))
    if isinstance(e, DatabaseError):
        if e.orig.diag.sqlstate == IMMUTABLE_ROW_ERROR:
            raise ImmutableRowData(detail=e.orig.diag.message_primary)
    if isinstance(e, ValidationError):
        raise PydanticError(detail=e.errors())
    if isinstance(e, APIException):
        raise e
    else:
        logException(e)
        raise e


class PydanticError(APIException):
    status_code = status.HTTP_422_UNPROCESSABLE_ENTITY
    headers = {"X-Error": "PydanticError"}

    def __init__(self, detail: str):
        super().__init__(detail=detail)


class ImmutableRowData(APIException):
    status_code = status.HTTP_406_NOT_ACCEPTABLE
    headers = {"X-Error": "ImmutableRowData"}

    def __init__(self, detail: str):
        super().__init__(detail=detail)


class UniqueViolation(APIException):
    status_code = status.HTTP_409_CONFLICT
    headers = {"X-Error": "UniqueViolation"}

    def __init__(self, detail: str):
        super().__init__(detail=detail)


class ForeignKeyViolation(APIException):
    status_code = status.HTTP_422_UNPROCESSABLE_ENTITY
    headers = {"X-Error": "ForeignKeyViolation"}

    def __init__(self, detail: str):
        super().__init__(detail=detail)
