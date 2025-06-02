from enum import IntEnum


class AccountStatus(IntEnum):
    ACTIVE = 1
    SUSPENDED = 2


class GenderType(IntEnum):
    OTHER = 1
    FEMALE = 2
    MALE = 3
    TRANSGENDER = 4
