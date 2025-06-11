from enum import IntEnum


class OrderIn(IntEnum):
    ASC = 1
    DESC = 2


class AccountStatus(IntEnum):
    ACTIVE = 1
    SUSPENDED = 2


class GenderType(IntEnum):
    OTHER = 1
    FEMALE = 2
    MALE = 3
    TRANSGENDER = 4


class PlatformType(IntEnum):
    OTHER = 1
    WEB = 2
    NATIVE = 3
    SERVER = 4


class LandmarkType(IntEnum):
    LOCAL = 1
    VILLAGE = 2
    DISTRICT = 3
    STATE = 4
    NATIONAL = 5


class BusinessStatus(IntEnum):
    ACTIVE = 1
    SUSPENDED = 2
    BLOCKED = 3


class BusinessType(IntEnum):
    OTHER = 1
    ORGANIZATION = 2
    INDIVIDUAL = 3


class CompanyStatus(IntEnum):
    UNDER_VERIFICATION = 1
    VERIFIED = 2
    SUSPENDED = 3


class CompanyType(IntEnum):
    OTHER = 1
    PRIVATE = 2
    GOVERNMENT = 3


class FareScope(IntEnum):
    GLOBAL = 1
    LOCAL = 2


class BankAccountType(IntEnum):
    OTHER = 1
    SAVINGS_ACCOUNT = 2
    CURRENT_ACCOUNT = 3
    SALARY_ACCOUNT = 4


class BusStatus(IntEnum):
    ACTIVE = 1
    MAINTENANCE = 2
    SUSPENDED = 3
