"""Secure password hashing utilities using Argon2id.

This module provides password hashing and verification using the Argon2id algorithm
with RFC 9106 recommended parameters for high-security applications.

Security features:
- Argon2id algorithm (PHC 2015 winner, OWASP recommended)
- RFC 9106 low-memory profile (64 MiB memory, 3 iterations)
- Automatic rehashing detection when parameters change
- Constant-time verification to prevent timing attacks
"""

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError
from argon2.profiles import RFC_9106_LOW_MEMORY

ph = PasswordHasher.from_parameters(RFC_9106_LOW_MEMORY)


async def get_password_hash(password: str | bytes) -> str:
    """Hash a password using Argon2id with RFC 9106 parameters.

    Args:
        password: Plain text password to hash. Can be str or bytes.

    Returns:
        Argon2id hash string in PHC format (e.g., $argon2id$v=19$m=2097152,t=1,p=4$...).
    """
    if isinstance(password, bytes):
        password = password.decode("utf-8")
    return ph.hash(password)


async def verify_password(plain_password: str | bytes, hashed_password: str) -> bool:
    """Verify a password against a hash using constant-time comparison.

    Args:
        plain_password: Plain text password to verify.
        hashed_password: Argon2 hash to check against.

    Returns:
        True if password matches, False otherwise.

    Note:
        This function uses constant-time comparison to prevent timing attacks.
        Invalid hash formats return False rather than raising exceptions to
        avoid information leakage about hash validity.
    """
    if isinstance(plain_password, bytes):
        plain_password = plain_password.decode("utf-8")
    try:
        ph.verify(hashed_password, plain_password)
    except VerifyMismatchError:
        return False
    except (InvalidHashError, VerificationError):
        return False
    return True


def check_needs_rehash(hashed_password: str) -> bool:
    """Check if a password hash needs to be rehashed due to parameter changes.

    This should be called after successful verification to detect if the hash
    was created with older/weaker parameters and needs to be upgraded.

    Args:
        hashed_password: The hash to check.

    Returns:
        True if the hash should be regenerated with current parameters.

    Example:
        ```python
        if await verify_password(password, stored_hash):
            if check_needs_rehash(stored_hash):
                new_hash = await get_password_hash(password)
                # Update stored_hash in database
        ```
    """
    try:
        return ph.check_needs_rehash(hashed_password)
    except InvalidHashError:
        return True
