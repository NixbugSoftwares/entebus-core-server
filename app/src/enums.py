from enum import IntEnum


class AccountStatus(IntEnum):
    ACTIVE = 1
    SUSPENDED = 2


class GenderType(IntEnum):
    OTHER = 1
    FEMALE = 2
    MALE = 3
    TRANSGENDER = 4


class CompanyStatus(IntEnum):
    UNDER_VERIFICATION = 1
    VERIFIED = 2
    SUSPENDED = 3


class CompanyType(IntEnum):
    PRIVATE = 1
    GOVERNMENT = 2
    OTHER = 3
