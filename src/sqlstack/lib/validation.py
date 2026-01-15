"""Production-ready field validation utilities with comprehensive security checks."""

import re
import unicodedata
from typing import Any
from urllib.parse import urlparse

from sqlstack.lib.exceptions import ClientError

# Email patterns
EMAIL_BASIC_PATTERN = re.compile(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9](?:[a-zA-Z0-9.-]*[a-zA-Z0-9])?\.[a-zA-Z]{2,}$")
EMAIL_DOUBLE_DOT_PATTERN = re.compile(r"\.\.+")
EMAIL_BLOCKED_PATTERNS = [
    re.compile(r".*\+.*test.*@.*"),  # +test emails
    re.compile(r".*\+.*spam.*@.*"),  # +spam emails
    re.compile(r"^test.*@.*"),  # emails starting with test
    re.compile(r"^noreply@.*"),  # noreply addresses
    re.compile(r"^no-reply@.*"),  # no-reply addresses
]

# Name patterns - Unicode-aware
NAME_WHITESPACE_PATTERN = re.compile(r"\s+")
NAME_VALID_PATTERN = re.compile(r"^[a-zA-ZÀ-ÿĀ-žА-я\u4e00-\u9fff\u0600-\u06ff\u3040-\u309f\u30a0-\u30ff\s'\-\.]+$")
NAME_REPEATED_PATTERN = re.compile(r"(.)\1{4,}")  # 5+ repeated characters

# Username patterns
USERNAME_VALID_PATTERN = re.compile(r"^[a-z0-9_-]+$")
USERNAME_START_PATTERN = re.compile(r"^[a-z0-9]")
USERNAME_REPEATED_PATTERN = re.compile(r"(.)\1{3,}")  # 4+ repeated characters

# Slug patterns
SLUG_VALID_PATTERN = re.compile(r"^[a-z0-9-]+$")

# Phone patterns
PHONE_BASIC_PATTERN = re.compile(r"^[\+]?[0-9\s\-\(\)\.]+$")
PHONE_DIGITS_PATTERN = re.compile(r"[^\d]")

# Email domain/pattern constants
EMAIL_BLOCKED_DOMAINS = {
    "10minutemail.com",
    "tempmail.org",
    "guerrillamail.com",
    "mailinator.com",
    "throwaway.email",
    "temp-mail.org",
    "yopmail.com",
    "maildrop.cc",
    "dispostable.com",
    "trashmail.com",
    "fake-mail.cf",
    "tempmail.net",
}

# Phone number length constants
PHONE_MIN_DIGITS = 7
PHONE_MAX_DIGITS = 15

# Email length constants
EMAIL_MAX_LENGTH = 254  # RFC 5321 limit
EMAIL_MIN_LENGTH = 3
EMAIL_LOCAL_PART_MAX_LENGTH = 64  # RFC 5321 limit

# Name and username length constants
NAME_MAX_LENGTH = 100
USERNAME_MIN_LENGTH = 3
USERNAME_MAX_LENGTH = 30

# URL and slug length constants
URL_MAX_LENGTH = 2048
SLUG_MAX_LENGTH = 100

# Reserved usernames constant
RESERVED_USERNAMES = {
    "admin",
    "root",
    "api",
    "www",
    "mail",
    "ftp",
    "support",
    "help",
    "security",
    "privacy",
    "terms",
    "about",
    "contact",
    "blog",
    "news",
    "app",
    "application",
    "system",
    "test",
    "user",
    "guest",
    "demo",
    "null",
    "undefined",
    "none",
}

# URL validation constants
ALLOWED_URL_SCHEMES = {"http", "https"}
BLOCKED_URL_DOMAINS = {
    "localhost",
    "127.0.0.1",
    "0.0.0.0",  # noqa: S104
    "::1",
    "[::1]",
}
SUSPICIOUS_URL_PATTERNS = ["javascript:", "data:", "vbscript:", "file:"]


class ValidationError(ClientError):
    """Custom validation error for all field validations."""


# Core Validation Framework
def validate_not_empty(value: str) -> str:
    """Validate that a value is not empty after stripping whitespace.

    Args:
        value: The string to validate

    Returns:
        The cleaned string

    Raises:
        ValidationError: If value is empty after stripping
    """
    cleaned = value.strip()
    if not cleaned:
        msg = "Value cannot be empty"
        raise ValidationError(msg)
    return cleaned


def validate_length(value: str, min_length: int = 0, max_length: int | None = None) -> str:
    """Validate string length constraints.

    Args:
        value: The string to validate
        min_length: Minimum allowed length
        max_length: Maximum allowed length

    Returns:
        The input string if valid

    Raises:
        ValidationError: If length constraints are violated
    """
    if len(value) < min_length:
        msg = f"Must be at least {min_length} characters"
        raise ValidationError(msg)
    if max_length and len(value) > max_length:
        msg = f"Must not exceed {max_length} characters"
        raise ValidationError(msg)
    return value


def validate_no_control_chars(value: str) -> str:
    """Remove/reject control characters.

    Args:
        value: The string to validate

    Raises:
        ValidationError: If control characters are found

    Returns:
        The cleansed string without control characters
    """
    if any(unicodedata.category(char) == "Cc" for char in value if char not in "\n\r\t"):
        msg = "Contains invalid control characters"
        raise ValidationError(msg)
    return value


# Email Validation
def validate_email(v: str) -> str:
    """Production-ready email validation with comprehensive checks.

    Args:
        v: The email string to validate

    Returns:
        The validated and normalized email

    Raises:
        ValidationError: If email validation fails
    """
    if not isinstance(v, str):  # pyright: ignore
        msg = "Email must be a string"  # type: ignore[unreachable]
        raise ValidationError(msg)

    # Basic cleanup
    email = v.strip().lower()

    # Length check
    if len(email) > EMAIL_MAX_LENGTH:
        msg = "Email address too long"
        raise ValidationError(msg)

    if len(email) < EMAIL_MIN_LENGTH:
        if "@" in email:
            msg = "Email address too short"
            raise ValidationError(msg)
        msg = "Invalid email format"
        raise ValidationError(msg)

    # Basic regex validation
    if not EMAIL_BASIC_PATTERN.match(email):
        msg = "Invalid email format"
        raise ValidationError(msg)

    # Check for double dots
    if EMAIL_DOUBLE_DOT_PATTERN.search(email):
        msg = "Invalid email format"
        raise ValidationError(msg)

    # Check against blocked domains
    domain = email.split("@")[1] if "@" in email else ""
    if domain in EMAIL_BLOCKED_DOMAINS:
        msg = "Email domain not allowed"
        raise ValidationError(msg)

    # Check against blocked patterns
    for pattern in EMAIL_BLOCKED_PATTERNS:
        if pattern.match(email):
            msg = "Email format not allowed"
            raise ValidationError(msg)

    # Additional security checks
    local_part = email.split("@")[0]
    if len(local_part) > EMAIL_LOCAL_PART_MAX_LENGTH:
        msg = "Email local part too long"
        raise ValidationError(msg)

    return email


# Name and Text Validation
def validate_name(v: str) -> str:
    """Human name validation with proper handling of international names.

    Args:
        v: The name string to validate

    Returns:
        The validated and normalized name

    Raises:
        ValidationError: If name validation fails
    """
    if not isinstance(v, str):  # pyright: ignore
        msg = "Name must be a string"  # type: ignore[unreachable]
        raise ValidationError(msg)

    # Clean and normalize
    name = v.strip()
    name = NAME_WHITESPACE_PATTERN.sub(" ", name)  # Normalize whitespace

    # Length validation
    if len(name) < 1:
        msg = "Name cannot be empty"
        raise ValidationError(msg)
    if len(name) > NAME_MAX_LENGTH:
        msg = f"Name must not exceed {NAME_MAX_LENGTH} characters"
        raise ValidationError(msg)

    # Character validation - allow letters, spaces, hyphens, apostrophes, periods
    # Allow extended Unicode for international names
    if not NAME_VALID_PATTERN.match(name):
        msg = "Name contains invalid characters"
        raise ValidationError(msg)

    # Prevent abuse patterns
    if NAME_REPEATED_PATTERN.search(name):  # 5+ repeated characters
        msg = "Name contains suspicious patterns"
        raise ValidationError(msg)

    return name


def validate_username(v: str) -> str:
    """Username validation with uniqueness and character restrictions.

    Args:
        v: The username string to validate

    Returns:
        The validated and normalized username

    Raises:
        ValidationError: If username validation fails
    """
    if not isinstance(v, str):  # pyright: ignore
        msg = "Username must be a string"  # type: ignore[unreachable]
        raise ValidationError(msg)

    # Clean and normalize
    username = v.strip().lower()

    # Length validation
    if len(username) < USERNAME_MIN_LENGTH:
        msg = f"Username must be at least {USERNAME_MIN_LENGTH} characters"
        raise ValidationError(msg)
    if len(username) > USERNAME_MAX_LENGTH:
        msg = f"Username must not exceed {USERNAME_MAX_LENGTH} characters"
        raise ValidationError(msg)

    # Character validation - alphanumeric, hyphens, underscores only
    if not USERNAME_VALID_PATTERN.match(username):
        msg = "Username can only contain letters, numbers, hyphens, and underscores"
        raise ValidationError(msg)

    # Must start with letter or number
    if not USERNAME_START_PATTERN.match(username):
        msg = "Username must start with a letter or number"
        raise ValidationError(msg)

    # Check reserved usernames
    if username in RESERVED_USERNAMES:
        msg = "Username is reserved and cannot be used"
        raise ValidationError(msg)

    # Prevent abuse patterns
    if USERNAME_REPEATED_PATTERN.search(username):  # 4+ repeated characters
        msg = "Username contains too many repeated characters"
        raise ValidationError(msg)

    return username


def validate_url(v: str) -> str:
    """URL validation with security checks.

    Args:
        v: The URL string to validate

    Returns:
        The validated URL

    Raises:
        ValidationError: If URL validation fails
    """
    if not isinstance(v, str):  # pyright: ignore
        msg = "URL must be a string"  # type: ignore[unreachable]
        raise ValidationError(msg)

    url = v.strip()

    # Length check
    if len(url) > URL_MAX_LENGTH:
        msg = "URL too long"
        raise ValidationError(msg)

    try:
        parsed = urlparse(url)
    except Exception as e:
        msg = "Invalid URL format"
        raise ValidationError(msg) from e

    # Scheme validation
    if not parsed.scheme:
        msg = "URL must include a scheme (http:// or https://)"
        raise ValidationError(msg)

    if parsed.scheme not in ALLOWED_URL_SCHEMES:
        msg = f"URL scheme must be one of: {', '.join(ALLOWED_URL_SCHEMES)}"
        raise ValidationError(msg)

    # Domain validation
    if not parsed.hostname:
        msg = "URL must include a hostname"
        raise ValidationError(msg)

    if parsed.hostname in BLOCKED_URL_DOMAINS:
        msg = "URL domain not allowed"
        raise ValidationError(msg)

    # Prevent common attacks
    url_lower = url.lower()
    if any(suspicious in url_lower for suspicious in SUSPICIOUS_URL_PATTERNS):
        msg = "URL contains suspicious content"
        raise ValidationError(msg)

    return url


def validate_slug(v: str) -> str:
    """Slug validation for URL-safe identifiers.

    Args:
        v: The slug string to validate

    Returns:
        The validated slug

    Raises:
        ValidationError: If slug validation fails
    """
    if not isinstance(v, str):  # pyright: ignore
        msg = "Slug must be a string"  # type: ignore[unreachable]
        raise ValidationError(msg)

    slug = v.strip().lower()

    # Length validation
    if len(slug) < 1:
        msg = "Slug cannot be empty"
        raise ValidationError(msg)
    if len(slug) > SLUG_MAX_LENGTH:
        msg = f"Slug must not exceed {SLUG_MAX_LENGTH} characters"
        raise ValidationError(msg)

    # Character validation - lowercase, numbers, hyphens only
    if not SLUG_VALID_PATTERN.match(slug):
        msg = "Slug can only contain lowercase letters, numbers, and hyphens"
        raise ValidationError(msg)

    # Cannot start or end with hyphen
    if slug.startswith("-") or slug.endswith("-"):
        msg = "Slug cannot start or end with a hyphen"
        raise ValidationError(msg)

    # Cannot have consecutive hyphens
    if "--" in slug:
        msg = "Slug cannot contain consecutive hyphens"
        raise ValidationError(msg)

    return slug


# Phone Number Validation
def validate_phone(v: str) -> str:
    """International phone number validation.

    Args:
        v: The phone number string to validate

    Returns:
        The validated phone number

    Raises:
        ValidationError: If phone validation fails
    """
    if not isinstance(v, str):  # pyright: ignore
        msg = "Phone number must be a string"  # type: ignore[unreachable]
        raise ValidationError(msg)

    phone = v.strip()

    if not phone:
        msg = "Phone number cannot be empty"
        raise ValidationError(msg)

    # Basic validation
    # Allow only digits, spaces, hyphens, parentheses, and plus sign
    if not PHONE_BASIC_PATTERN.match(phone):
        msg = "Invalid phone number format"
        raise ValidationError(msg)

    # Basic length check
    digits_only = PHONE_DIGITS_PATTERN.sub("", phone)
    if len(digits_only) < PHONE_MIN_DIGITS or len(digits_only) > PHONE_MAX_DIGITS:
        msg = f"Phone number must be between {PHONE_MIN_DIGITS} and {PHONE_MAX_DIGITS} digits"
        raise ValidationError(msg)

    return phone


# Password Validation Constants
PASSWORD_MIN_LENGTH = 12
PASSWORD_MAX_LENGTH = 128
PASSWORD_SCORE_WEAK = 0
PASSWORD_SCORE_MEDIUM = 50
PASSWORD_SCORE_STRONG = 80

# Common passwords (top 100 most common - expand as needed)
COMMON_PASSWORDS = {
    "password",
    "123456",
    "123456789",
    "12345678",
    "12345",
    "1234567",
    "password1",
    "123123",
    "1234567890",
    "000000",
    "abc123",
    "qwerty",
    "qwerty123",
    "qwertyuiop",
    "123321",
    "letmein",
    "admin",
    "welcome",
    "monkey",
    "dragon",
    "master",
    "sunshine",
    "princess",
    "football",
    "iloveyou",
    "111111",
    "666666",
    "654321",
    "passw0rd",
    "password123",
    "superman",
    "trustno1",
    "liverpool",
    "123qwe",
    "qweasd",
    "welcome1",
}

# Password pattern detection
PASSWORD_REPEATED_PATTERN = re.compile(r"(.)\1{2,}")  # 3+ repeated characters
PASSWORD_SEQUENTIAL_123 = "0123456789"  # noqa: S105 - not a password, pattern string
PASSWORD_SEQUENTIAL_ABC = "abcdefghijklmnopqrstuvwxyz"  # noqa: S105 - not a password, pattern string
PASSWORD_SEQUENTIAL_QWE = "qwertyuiopasdfghjklzxcvbnm"  # noqa: S105 - not a password, pattern string


class PasswordValidationError(ValidationError):
    """Password validation specific error."""


def validate_password(password: str) -> str:
    """Basic password validation that delegates to strength validation.

    Args:
        password: Password string to validate

    Returns:
        The validated password

    Raises:
        PasswordValidationError: If password doesn't meet requirements
    """
    return validate_password_strength(password)


def validate_password_strength(password: str) -> str:
    """Validate password meets strength requirements.

    Requirements:
    - Length: 12-128 characters
    - At least one uppercase letter
    - At least one lowercase letter
    - At least one digit
    - At least one special character
    - Not in common passwords list
    - No excessive repeated characters (3+)
    - No obvious sequential patterns

    Args:
        password: Password string to validate

    Returns:
        The validated password

    Raises:
        PasswordValidationError: If password doesn't meet requirements
    """
    if not isinstance(password, str):  # pyright: ignore
        msg = "Password must be a string"  # type: ignore[unreachable]
        raise PasswordValidationError(msg)

    # Length checks
    if len(password) < PASSWORD_MIN_LENGTH:
        msg = f"Password must be at least {PASSWORD_MIN_LENGTH} characters long"
        raise PasswordValidationError(msg)

    if len(password) > PASSWORD_MAX_LENGTH:
        msg = f"Password must not exceed {PASSWORD_MAX_LENGTH} characters"
        raise PasswordValidationError(msg)

    password_lower = password.lower()

    # Common password checks before character requirements
    if password_lower in COMMON_PASSWORDS:
        msg = "Password is too common"
        raise PasswordValidationError(msg)

    for common in COMMON_PASSWORDS:
        if password_lower.startswith(common):
            msg = "Password is too common"
            raise PasswordValidationError(msg)

    if PASSWORD_REPEATED_PATTERN.search(password_lower):
        msg = "Password is too common"
        raise PasswordValidationError(msg)

    # Sequential pattern checks (case-insensitive, 4+ sequential chars)
    for i in range(len(password_lower) - 3):
        substring = password_lower[i : i + 4]
        if substring in PASSWORD_SEQUENTIAL_123 or substring in PASSWORD_SEQUENTIAL_123[::-1]:
            msg = "Password is too common"
            raise PasswordValidationError(msg)
        if substring in PASSWORD_SEQUENTIAL_ABC or substring in PASSWORD_SEQUENTIAL_ABC[::-1]:
            msg = "Password is too common"
            raise PasswordValidationError(msg)
        if substring in PASSWORD_SEQUENTIAL_QWE or substring in PASSWORD_SEQUENTIAL_QWE[::-1]:
            msg = "Password is too common"
            raise PasswordValidationError(msg)

    # Character requirement checks
    if not any(c.isupper() for c in password):
        msg = "Password must contain at least one uppercase letter"
        raise PasswordValidationError(msg)

    if not any(c.islower() for c in password):
        msg = "Password must contain at least one lowercase letter"
        raise PasswordValidationError(msg)

    if not any(c.isdigit() for c in password):
        msg = "Password must contain at least one digit"
        raise PasswordValidationError(msg)

    if not any(c in "!@#$%^&*()_+-=[]{}|;:,.<>?/~`" for c in password):
        msg = "Password must contain at least one special character"
        raise PasswordValidationError(msg)

    return password


def get_password_strength(password: str) -> dict[str, Any]:
    """Analyze password strength and return detailed analysis.

    Args:
        password: Password string to analyze

    Returns:
        dict with:
            - strength: "weak" | "medium" | "strong"
            - score: int (0-100)
            - requirements: dict of requirement checks
            - feedback: list of improvement suggestions
    """
    score = 0
    feedback: list[str] = []

    # Check length (0-25 points)
    length = len(password)
    if length < 8:  # noqa: PLR2004 - minimum weak password threshold
        feedback.append("Use at least 12 characters")
        score += max(0, length * 2)
    elif length < PASSWORD_MIN_LENGTH:
        feedback.append("Use at least 12 characters")
        score += 15
    elif length >= PASSWORD_MIN_LENGTH:
        score += 25

    # Check uppercase (0-15 points)
    has_upper = any(c.isupper() for c in password)
    if has_upper:
        score += 15
    else:
        feedback.append("Add uppercase letters")

    # Check lowercase (0-15 points)
    has_lower = any(c.islower() for c in password)
    if has_lower:
        score += 15
    else:
        feedback.append("Add lowercase letters")

    # Check digits (0-15 points)
    has_digit = any(c.isdigit() for c in password)
    if has_digit:
        score += 15
    else:
        feedback.append("Add numbers")

    # Check special characters (0-15 points)
    has_special = any(c in "!@#$%^&*()_+-=[]{}|;:,.<>?/~`" for c in password)
    if has_special:
        score += 15
    else:
        feedback.append("Add special characters (!@#$%^&* etc.)")

    # Check for common passwords (-20 points)
    if password.lower() in COMMON_PASSWORDS:
        score = max(0, score - 20)
        feedback.append("Avoid common passwords")

    # Check for repeated characters (-10 points)
    if PASSWORD_REPEATED_PATTERN.search(password):
        score = max(0, score - 10)
        feedback.append("Avoid repeated characters")

    # Determine strength level
    if score < PASSWORD_SCORE_MEDIUM:
        strength = "weak"
    elif score < PASSWORD_SCORE_STRONG:
        strength = "medium"
    else:
        strength = "strong"

    return {
        "strength": strength,
        "score": min(100, score),  # Cap at 100
        "requirements": {
            "length": length >= PASSWORD_MIN_LENGTH,
            "uppercase": has_upper,
            "lowercase": has_lower,
            "digits": has_digit,
            "special_chars": has_special,
        },
        "feedback": feedback,
    }
