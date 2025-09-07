"""
Centralized exception handling for EnteBus API.

This module provides:
- Base APIException class extending FastAPI's HTTPException.
- Custom domain-specific exceptions with appropriate status codes and headers.
- Utility functions for formatting DB errors, logging, and routing exceptions.

Usage:
    - Raise specific exceptions in route handlers or services.
    - Use `handle()` to normalize raw exceptions (DB, Redis, Pydantic) into API-friendly responses.
"""

from traceback import format_exception
from logging import getLogger
from fastapi import status, HTTPException
from sqlalchemy.exc import IntegrityError
from psycopg2.errorcodes import UNIQUE_VIOLATION, FOREIGN_KEY_VIOLATION
from pydantic import ValidationError
from redis.exceptions import RedisError
from sqlalchemy import Column


# ---------------------------------------------------------------------------
# Utility functions
# ---------------------------------------------------------------------------
def formatIntegrityError(e: IntegrityError) -> str:
    """
    Format a database integrity error into a user-friendly message.
    """
    errorMessage: str = e.orig.diag.message_detail
    errorMessage = errorMessage.translate({ord(i): None for i in '\\"\\.\\(\\)'})
    errorMessage = errorMessage.replace("Key ", "For ")
    errorMessage = errorMessage.replace("=", " value ")
    return errorMessage


def logException(e: Exception) -> None:
    """Log an exception with traceback using Uvicorn's error logger."""
    detail = str(format_exception(type(e), e, e.__traceback__))
    logger = getLogger("uvicorn.error")
    logger.error(detail)


# ---------------------------------------------------------------------------
# Base Exception
# ---------------------------------------------------------------------------
class APIException(HTTPException):
    """
    Base class for all application-specific exceptions.

    Provides default handling of status_code, detail, and headers.
    """

    status_code = status.HTTP_400_BAD_REQUEST
    detail = None
    headers = None

    def __init__(self, *args, **kwargs):
        kwargs.setdefault("status_code", self.status_code)
        kwargs.setdefault("detail", self.detail)
        kwargs.setdefault("headers", self.headers)
        super().__init__(*args, **kwargs)


# ---------------------------------------------------------------------------
# Exception handling entrypoint
# ---------------------------------------------------------------------------
def handle(e: Exception):
    """
    Normalize and re-raise exceptions as API-friendly errors.

    Converts raw exceptions from DB, Pydantic, Redis, etc. into
    corresponding APIException subclasses.
    """
    if isinstance(e, IntegrityError):
        if e.orig.diag.sqlstate == UNIQUE_VIOLATION:
            raise UniqueViolation(formatIntegrityError(e))
        if e.orig.diag.sqlstate == FOREIGN_KEY_VIOLATION:
            raise ForeignKeyViolation(formatIntegrityError(e))
    if isinstance(e, ValidationError):
        raise PydanticError(detail=e.errors())
    if isinstance(e, APIException):
        raise e
    if isinstance(e, RedisError):
        raise RedisDBError(detail=str(e))

    logException(e)
    raise e


# ---------------------------------------------------------------------------
# Exception Classes
# ---------------------------------------------------------------------------
class PydanticError(APIException):
    status_code = status.HTTP_422_UNPROCESSABLE_ENTITY
    headers = {"X-Error": "PydanticError"}

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


class UnknownValue(APIException):
    status_code = status.HTTP_404_NOT_FOUND
    headers = {"X-Error": "UnknownValue"}

    def __init__(self, column_name: Column):
        detail = f"Invalid {column_name.name} is provided"
        super().__init__(detail=detail)


class InvalidValue(APIException):
    status_code = status.HTTP_406_NOT_ACCEPTABLE
    headers = {"X-Error": "InvalidValue"}

    def __init__(self, column_name: Column):
        detail = f"Invalid {column_name.name} is provided"
        super().__init__(detail=detail)


class InvalidCredentials(APIException):
    status_code = status.HTTP_401_UNAUTHORIZED
    detail = "Invalid username or password"
    headers = {"X-Error": "InvalidCredentials"}


class InactiveAccount(APIException):
    status_code = status.HTTP_412_PRECONDITION_FAILED
    detail = "The account is not in active status"
    headers = {"X-Error": "InactiveAccount"}


class InvalidToken(APIException):
    status_code = status.HTTP_401_UNAUTHORIZED
    detail = "Invalid token"
    headers = {"X-Error": "InvalidToken"}


class NoPermission(APIException):
    status_code = status.HTTP_403_FORBIDDEN
    detail = "This user has no permission to perform this action"
    headers = {"X-Error": "NoPermission"}


class InvalidIdentifier(APIException):
    status_code = status.HTTP_404_NOT_FOUND
    detail = "Invalid ID provided"
    headers = {"X-Error": "InvalidIdentifier"}


class InvalidWKTStringOrType(APIException):
    status_code = status.HTTP_406_NOT_ACCEPTABLE
    detail = "Invalid WKT string or type"
    headers = {"X-Error": "InvalidWKTStringOrType"}


class InvalidSRID4326(APIException):
    status_code = status.HTTP_406_NOT_ACCEPTABLE
    detail = "The SRID of the geometry is not 4326"
    headers = {"X-Error": "InvalidSRID4326"}


class InvalidAABB(APIException):
    status_code = status.HTTP_406_NOT_ACCEPTABLE
    detail = "The geometry is not a valid Axis-Aligned Bounding Box"
    headers = {"X-Error": "InvalidAABB"}


class OverlappingLandmarkBoundary(APIException):
    status_code = status.HTTP_406_NOT_ACCEPTABLE
    detail = "Boundary overlapping with other landmarks boundary"
    headers = {"X-Error": "OverlappingLandmarkBoundary"}


class InvalidBoundaryArea(APIException):
    status_code = status.HTTP_406_NOT_ACCEPTABLE
    detail = "Boundary area not within the prescribed limits"
    headers = {"X-Error": "InvalidBoundaryArea"}


class BusStopOutsideLandmark(APIException):
    status_code = status.HTTP_406_NOT_ACCEPTABLE
    detail = "The bus stop location is not within the landmark boundary"
    headers = {"X-Error": "BusStopOutsideLandmark"}


class InvalidStateTransition(APIException):
    status_code = status.HTTP_406_NOT_ACCEPTABLE
    headers = {"X-Error": "InvalidStateTransition"}

    def __init__(self, column_name: Column):
        detail = f"The {column_name.name} cannot be set to the provided value"
        super().__init__(detail=detail)


class InvalidAssociation(APIException):
    status_code = status.HTTP_406_NOT_ACCEPTABLE
    headers = {"X-Error": "InvalidAssociation"}

    def __init__(self, column_name_1: Column, column_name_2: Column):
        detail = f"The {column_name_1.name} is not associated with {column_name_2.name}"
        super().__init__(detail=detail)


class InvalidRoute(APIException):
    status_code = status.HTTP_406_NOT_ACCEPTABLE
    detail = "Route is not usable"
    headers = {"X-Error": "UnusableRoute"}


class InactiveResource(APIException):
    status_code = status.HTTP_412_PRECONDITION_FAILED
    headers = {"X-Error": "InactiveResource"}

    def __init__(self, orm_class):
        detail = (
            f"The status of {orm_class.__name__} is not in an active or useful state"
        )
        super().__init__(detail=detail)


class DataInUse(APIException):
    status_code = status.HTTP_406_NOT_ACCEPTABLE
    headers = {"X-Error": "DataInUse"}

    def __init__(self, orm_class):
        detail = f"The {orm_class.__name__} is currently in use"
        super().__init__(detail=detail)


class MissingParameter(APIException):
    status_code = status.HTTP_406_NOT_ACCEPTABLE
    headers = {"X-Error": "MissingParameter"}

    def __init__(self, column_name: Column):
        detail = f"The {column_name.name} is missing"
        super().__init__(detail=detail)


class UnexpectedParameter(APIException):
    status_code = status.HTTP_406_NOT_ACCEPTABLE
    headers = {"X-Error": "UnexpectedParameter"}

    def __init__(self, column_name: Column):
        detail = f"Unexpected parameter {column_name.name} is provided"
        super().__init__(detail=detail)


class InvalidFareFunction(APIException):
    status_code = status.HTTP_406_NOT_ACCEPTABLE
    detail = "Invalid fare function"
    headers = {"X-Error": "InvalidFareFunction"}


class UnknownTicketType(APIException):
    status_code = status.HTTP_406_NOT_ACCEPTABLE
    headers = {"X-Error": "UnknownTicketType"}

    def __init__(self, ticket_type_name: str):
        detail = (
            f"Ticket type '{ticket_type_name}' cannot be validated using the function"
        )
        super().__init__(detail=detail)


class JSTimeLimitExceeded(APIException):
    status_code = status.HTTP_406_NOT_ACCEPTABLE
    headers = {"X-Error": "JSTimeout"}
    detail = "JavaScript execution timed out"


class JSMemoryLimitExceeded(APIException):
    status_code = status.HTTP_406_NOT_ACCEPTABLE
    headers = {"X-Error": "JSMemoryLimitExceeded"}
    detail = "JavaScript execution exceeded the allowed memory limit"


class LockAcquireTimeout(APIException):
    status_code = status.HTTP_406_NOT_ACCEPTABLE
    headers = {"X-Error": "LockAcquireTimeout"}
    detail = "Lock acquisition timed out"


class ExceededMaxLimit(APIException):
    status_code = status.HTTP_406_NOT_ACCEPTABLE
    headers = {"X-Error": "ExceededMaxLimit"}

    def __init__(self, orm_class):
        detail = f"Maximum limit for {orm_class.__name__} is exceeded"
        super().__init__(detail=detail)


class InvalidFareVersion(APIException):
    status_code = status.HTTP_406_NOT_ACCEPTABLE
    headers = {"X-Error": "InvalidFareVersion"}
    detail = "Invalid dynamic fare version"


class DuplicateDuty(APIException):
    status_code = status.HTTP_406_NOT_ACCEPTABLE
    headers = {"X-Error": "DuplicateDuty"}

    def __init__(self, column_name_1: Column, column_name_2: Column):
        detail = f"The {column_name_1.name} already has a assigned duty for this {column_name_2.name}"
        super().__init__(detail=detail)


class InvalidImageFile(APIException):
    status_code = status.HTTP_406_NOT_ACCEPTABLE
    headers = {"X-Error": "InvalidImage"}
    detail = "Invalid image provided"


class RedisDBError(APIException):
    status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    headers = {"X-Error": "RedisAPIError"}

    def __init__(self, detail: str):
        super().__init__(detail=detail)
