from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

passwordHasher = PasswordHasher(encoding="utf-8")


def makePassword(password: str) -> str:
    """
    Hash a plain-text password using Argon2.

    Args:
        password (str): The plain-text password to be hashed.

    Returns:
        str: The Argon2 hash of the given password.
    """
    return passwordHasher.hash(password)


def checkPassword(password: str, actual_password: str) -> bool:
    """
    Verify a plain-text password against a stored Argon2 hash.

    Args:
        password (str): The plain-text password to check.
        actual_password (str): The stored Argon2 hash of the password.

    Returns:
        bool: True if the password matches the hash, False otherwise.
    """
    try:
        passwordHasher.verify(actual_password, password)
        return True
    except VerifyMismatchError:
        return False
