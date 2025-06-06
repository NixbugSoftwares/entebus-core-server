from enum import IntEnum


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


class OrderIn(IntEnum):
    ASC = 1
    DESC = 2
