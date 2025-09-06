"""
Enumerations for EnteBus Core Server.

These enums define standard codes used throughout the application,
including application IDs, account status, entity types, and operational states.
They are primarily used for:
    - Database storage (as integer codes).
    - API request/response validation.
    - Consistent state management across services.
"""

from enum import IntEnum


class AppID(IntEnum):
    """Identifiers for different applications within the EnteBus ecosystem."""

    EXECUTIVE = 1
    VENDOR = 2
    OPERATOR = 3
    PUBLIC = 4


class OrderIn(IntEnum):
    """Sorting order for queries or data presentation."""

    ASC = 1
    DESC = 2


class AccountStatus(IntEnum):
    """Status of an account (executive, operator, vendor, etc.)."""

    ACTIVE = 1
    SUSPENDED = 2


class GenderType(IntEnum):
    """Gender identifiers for user profiles."""

    OTHER = 1
    FEMALE = 2
    MALE = 3
    TRANSGENDER = 4


class PlatformType(IntEnum):
    """Platform used to access the system."""

    OTHER = 1
    WEB = 2
    NATIVE = 3
    SERVER = 4


class LandmarkType(IntEnum):
    """Administrative level or importance of a landmark"""

    LOCAL = 1
    VILLAGE = 2
    DISTRICT = 3
    STATE = 4
    NATIONAL = 5


class BusinessStatus(IntEnum):
    """Status of a registered business."""

    ACTIVE = 1
    SUSPENDED = 2
    BLOCKED = 3


class BusinessType(IntEnum):
    """Type of registered business entity."""

    OTHER = 1
    ORGANIZATION = 2
    INDIVIDUAL = 3


class CompanyStatus(IntEnum):
    """Verification and operational status of a company."""

    UNDER_VERIFICATION = 1
    VERIFIED = 2
    SUSPENDED = 3


class CompanyType(IntEnum):
    """Classification of companies."""

    OTHER = 1
    PRIVATE = 2
    GOVERNMENT = 3


class FareScope(IntEnum):
    """Scope of fare applicability."""

    GLOBAL = 1
    LOCAL = 2


class BankAccountType(IntEnum):
    """Supported types of bank accounts."""

    OTHER = 1
    SAVINGS_ACCOUNT = 2
    CURRENT_ACCOUNT = 3
    SALARY_ACCOUNT = 4


class BusStatus(IntEnum):
    """Operational status of a bus."""

    ACTIVE = 1
    MAINTENANCE = 2
    SUSPENDED = 3


class TicketingMode(IntEnum):
    """Modes of ticketing supported by the system."""

    HYBRID = 1
    DIGITAL = 2
    CONVENTIONAL = 3


class Day(IntEnum):
    """Days of the week (used for scheduling)."""

    MONDAY = 1
    TUESDAY = 2
    WEDNESDAY = 3
    THURSDAY = 4
    FRIDAY = 5
    SATURDAY = 6
    SUNDAY = 7


class TriggeringMode(IntEnum):
    """Service triggering configuration."""

    DISABLED = 1
    AUTO = 2
    MANUAL = 3


class ServiceStatus(IntEnum):
    """Lifecycle states of a service."""

    CREATED = 1
    STARTED = 2
    TERMINATED = 3
    ENDED = 4
    AUDITED = 5


class DutyStatus(IntEnum):
    """Lifecycle states of a duty."""

    ASSIGNED = 1
    STARTED = 2
    TERMINATED = 3
    ENDED = 4
    NOT_USED = 5


class RouteStatus(IntEnum):
    """Validation status of a route."""

    VALID = 1
    INVALID = 2
