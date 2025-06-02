from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

passwordHasher = PasswordHasher(encoding="utf-8")


def makePassword(password: str) -> str:
    return passwordHasher.hash(password)


def checkPassword(password: str, actual_password: str) -> bool:
    try:
        passwordHasher.verify(actual_password, password)
        return True
    except VerifyMismatchError:
        return False
