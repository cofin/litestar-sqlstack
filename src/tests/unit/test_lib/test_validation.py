"""Unit tests for validation utilities."""

from __future__ import annotations

import pytest

from sqlstack.utils.validation import (
    PASSWORD_MIN_LENGTH,
    PASSWORD_SCORE_MEDIUM,
    PASSWORD_SCORE_STRONG,
    PasswordValidationError,
    ValidationError,
    get_password_strength,
    validate_email,
    validate_length,
    validate_name,
    validate_no_control_chars,
    validate_not_empty,
    validate_password,
    validate_password_strength,
    validate_slug,
    validate_url,
    validate_username,
)


# Email validation tests
def test_valid_emails() -> None:
    """Test valid email addresses."""
    valid_emails = [
        "user@example.com",
        "user.email@domain.org",
        "user+tag@example.co.uk",
        "firstname.lastname@company.com",
        "a@b.co",
        "user123@example.com",
    ]

    for email in valid_emails:
        result = validate_email(email)
        assert result == email.lower()


def test_invalid_email_formats() -> None:
    """Test invalid email formats."""
    invalid_emails = [
        "invalid-email",
        "@example.com",
        "user@",
        "user..name@example.com",  # Double dot
        "user@example",  # No TLD
        "user@.example.com",  # Starts with dot
        "user@example..com",  # Double dot in domain
        "",
        "a",
        "user@example.c",  # TLD too short
    ]

    for email in invalid_emails:
        with pytest.raises(ValidationError, match="Invalid email format"):
            validate_email(email)


def test_blocked_email_domains() -> None:
    """Test blocked email domains."""
    blocked_emails = ["user@10minutemail.com", "user@tempmail.org", "fake@guerrillamail.com"]

    for email in blocked_emails:
        with pytest.raises(ValidationError, match="Email domain not allowed"):
            validate_email(email)


def test_blocked_email_patterns() -> None:
    """Test blocked email patterns."""
    blocked_emails = [
        "test.user@example.com",  # Starts with "test"
        "user+test@example.com",  # Contains "+test"
        "user+spam@example.com",  # Contains "+spam"
        "noreply@example.com",  # Starts with "noreply"
        "no-reply@example.com",  # Starts with "no-reply"
    ]

    for email in blocked_emails:
        with pytest.raises(ValidationError, match="Email format not allowed"):
            validate_email(email)


def test_email_length_limits() -> None:
    """Test email length validation."""
    # Too short
    with pytest.raises(ValidationError, match="Email address too short"):
        validate_email("a@")

    # Too long
    long_email = "a" * 250 + "@example.com"
    with pytest.raises(ValidationError, match="Email address too long"):
        validate_email(long_email)

    # Local part too long
    long_local = "a" * 65 + "@example.com"
    with pytest.raises(ValidationError, match="Email local part too long"):
        validate_email(long_local)


def test_email_case_normalization() -> None:
    """Test email case normalization."""
    result = validate_email("USER@EXAMPLE.COM")
    assert result == "user@example.com"


def test_non_string_email() -> None:
    """Test non-string email input."""
    with pytest.raises(ValidationError, match="Email must be a string"):
        validate_email(123)  # type: ignore[arg-type]


# Password validation tests
def test_valid_passwords() -> None:
    """Test valid passwords."""
    valid_passwords = [
        "MySecurePassword123!",
        "Another$trongP@ssw0rd",
        "ComplexPassw0rd#With$pecialChars",
        "Minimum12CharPass!",
    ]

    for password in valid_passwords:
        result = validate_password(password)
        assert result == password


def test_password_too_short() -> None:
    """Test password too short."""
    short_password = "Short1!"
    with pytest.raises(
        PasswordValidationError, match=f"Password must be at least {PASSWORD_MIN_LENGTH} characters long"
    ):
        validate_password_strength(short_password)


def test_password_too_long() -> None:
    """Test password too long."""
    long_password = "a" * 200
    with pytest.raises(PasswordValidationError, match="Password must not exceed"):
        validate_password_strength(long_password)


def test_password_missing_uppercase() -> None:
    """Test password missing uppercase letter."""
    with pytest.raises(PasswordValidationError, match="Password must contain at least one uppercase letter"):
        validate_password_strength("mysecurepassword123!")


def test_password_missing_lowercase() -> None:
    """Test password missing lowercase letter."""
    with pytest.raises(PasswordValidationError, match="Password must contain at least one lowercase letter"):
        validate_password_strength("MYSECUREPASSWORD123!")


def test_password_missing_digit() -> None:
    """Test password missing digit."""
    with pytest.raises(PasswordValidationError, match="Password must contain at least one digit"):
        validate_password_strength("MySecurePassword!")


def test_password_missing_special_char() -> None:
    """Test password missing special character."""
    with pytest.raises(PasswordValidationError, match="Password must contain at least one special character"):
        validate_password_strength("MySecurePassword123")


def test_common_passwords() -> None:
    """Test common password detection."""
    # Test exact matches from COMMON_PASSWORDS set that meet requirements
    basic_common = ["password", "qwerty", "123456789"]
    for password in basic_common:
        with pytest.raises(PasswordValidationError):  # Will fail on basic requirements first
            validate_password_strength(password)

    # Test pattern-based detection with passwords that start with common patterns
    pattern_passwords = [
        "123A!bcdefghijk",  # Starts with "123" which is detected
        "AbcA!efghijklmn",  # Starts with "abc" which is detected
        "QweA!rtyuiopqwe",  # Starts with "qwe" which is detected
    ]

    for password in pattern_passwords:
        with pytest.raises(PasswordValidationError, match="Password is too common"):
            validate_password_strength(password)


def test_repeated_character_patterns() -> None:
    """Test repeated character patterns."""
    with pytest.raises(PasswordValidationError, match="Password is too common"):
        validate_password_strength("Aaaaaaaaaaaaa1!")  # 13+ same character but meets basic requirements


def test_sequential_patterns() -> None:
    """Test sequential patterns."""
    sequential_passwords = [
        "123456789012A!",  # Sequential but with required chars
        "Abcdefghijkl1!",  # Sequential but with required chars
        "Qwertyuiopas1!",  # Sequential but with required chars
    ]

    for password in sequential_passwords:
        with pytest.raises(PasswordValidationError, match="Password is too common"):
            validate_password_strength(password)


def test_non_string_password() -> None:
    """Test non-string password input."""
    with pytest.raises(PasswordValidationError, match="Password must be a string"):
        validate_password_strength(123)  # type: ignore[arg-type]


# Password strength analysis tests
def test_weak_password_analysis() -> None:
    """Test weak password analysis."""
    analysis = get_password_strength("weak")

    assert analysis["strength"] == "weak"
    assert analysis["score"] < PASSWORD_SCORE_MEDIUM
    assert len(analysis["feedback"]) > 0


def test_medium_password_analysis() -> None:
    """Test medium strength password."""
    analysis = get_password_strength("MediumPass123!")

    assert analysis["strength"] in ["medium", "strong"]
    assert analysis["score"] >= PASSWORD_SCORE_MEDIUM


def test_strong_password_analysis() -> None:
    """Test strong password analysis."""
    analysis = get_password_strength("VeryStrongPassword123!@#$%")

    assert analysis["strength"] == "strong"
    assert analysis["score"] >= PASSWORD_SCORE_STRONG


def test_password_requirements_check() -> None:
    """Test password requirements checking."""
    analysis = get_password_strength("TestPassword123!")

    assert analysis["requirements"]["length"] is True
    assert analysis["requirements"]["uppercase"] is True
    assert analysis["requirements"]["lowercase"] is True
    assert analysis["requirements"]["digits"] is True
    assert analysis["requirements"]["special_chars"] is True


def test_password_feedback_generation() -> None:
    """Test feedback generation for weak passwords."""
    analysis = get_password_strength("weak")

    assert isinstance(analysis["feedback"], list)
    assert len(analysis["feedback"]) > 0
    assert any("characters" in feedback for feedback in analysis["feedback"])


# Name validation tests
def test_valid_names() -> None:
    """Test valid names."""
    valid_names = [
        "John Doe",
        "María García",
        "李小明",
        "Jean-Pierre",
        "O'Connor",
        "Dr. Smith",
        "José María",
        "François",
    ]

    for name in valid_names:
        result = validate_name(name)
        assert isinstance(result, str)
        assert len(result) > 0


def test_invalid_name_characters() -> None:
    """Test invalid characters in names."""
    invalid_names = [
        "John123",  # Numbers
        "Jane@Doe",  # @ symbol
        "User<script>",  # HTML
        "Name\x00",  # Control character (null)
    ]

    for name in invalid_names:
        with pytest.raises(ValidationError):
            validate_name(name)


def test_name_length_limits() -> None:
    """Test name length validation."""
    # Empty name
    with pytest.raises(ValidationError, match="Name cannot be empty"):
        validate_name("")

    # Too long name
    long_name = "a" * 101
    with pytest.raises(ValidationError, match="Name must not exceed"):
        validate_name(long_name)


def test_name_whitespace_normalization() -> None:
    """Test name whitespace normalization."""
    result = validate_name("  John    Doe  ")
    assert result == "John Doe"


def test_repeated_character_abuse() -> None:
    """Test repeated character abuse detection."""
    with pytest.raises(ValidationError, match="Name contains suspicious patterns"):
        validate_name("Johnnnnnnnn")


def test_non_string_name() -> None:
    """Test non-string name input."""
    with pytest.raises(ValidationError, match="Name must be a string"):
        validate_name(123)  # type: ignore[arg-type]


# Username validation tests
def test_valid_usernames() -> None:
    """Test valid usernames."""
    valid_usernames = ["john_doe", "user123", "test-user", "user_name_123", "a1b2c3"]

    for username in valid_usernames:
        result = validate_username(username)
        assert result == username.lower()


def test_invalid_username_characters() -> None:
    """Test invalid characters in usernames."""
    invalid_usernames = [
        "John Doe",  # Space
        "user@name",  # @ symbol
        "user.name",  # Dot
        "user!name",  # Special character
    ]

    for username in invalid_usernames:
        with pytest.raises(ValidationError, match="Username can only contain"):
            validate_username(username)

    # Test that UPPERCASE gets converted
    result = validate_username("UPPERCASE")
    assert result == "uppercase"


def test_username_length_limits() -> None:
    """Test username length validation."""
    # Too short
    with pytest.raises(ValidationError, match="Username must be at least"):
        validate_username("ab")

    # Too long
    long_username = "a" * 31
    with pytest.raises(ValidationError, match="Username must not exceed"):
        validate_username(long_username)


def test_username_start_character() -> None:
    """Test username must start with letter or number."""
    invalid_starts = ["_username", "-username"]

    for username in invalid_starts:
        with pytest.raises(ValidationError, match="Username must start with a letter or number"):
            validate_username(username)


def test_reserved_usernames() -> None:
    """Test reserved username blocking."""
    reserved_usernames = ["admin", "root", "api", "www", "support"]

    for username in reserved_usernames:
        with pytest.raises(ValidationError, match="Username is reserved"):
            validate_username(username)


def test_username_repeated_characters() -> None:
    """Test repeated character abuse detection."""
    with pytest.raises(ValidationError, match="Username contains too many repeated characters"):
        validate_username("userrrrrr")


def test_username_case_normalization() -> None:
    """Test username case normalization."""
    result = validate_username("UserName")
    assert result == "username"


def test_non_string_username() -> None:
    """Test non-string username input."""
    with pytest.raises(ValidationError, match="Username must be a string"):
        validate_username(123)  # type: ignore[arg-type]


# URL validation tests
def test_valid_urls() -> None:
    """Test valid URLs."""
    valid_urls = [
        "https://www.example.com",
        "http://example.org",
        "https://subdomain.example.com/path",
        "https://example.com/path?query=value#fragment",
    ]

    for url in valid_urls:
        result = validate_url(url)
        assert result == url


def test_invalid_url_schemes() -> None:
    """Test invalid URL schemes."""
    invalid_urls = [
        "ftp://example.com",
        "file:///etc/passwd",
        "javascript:alert('xss')",
        "data:text/html,<script>alert('xss')</script>",
    ]

    for url in invalid_urls:
        with pytest.raises(ValidationError):
            validate_url(url)


def test_missing_url_scheme() -> None:
    """Test URLs without scheme."""
    with pytest.raises(ValidationError, match="URL must include a scheme"):
        validate_url("example.com")


def test_missing_url_hostname() -> None:
    """Test URLs without hostname."""
    with pytest.raises(ValidationError, match="URL must include a hostname"):
        validate_url("https://")


def test_blocked_url_domains() -> None:
    """Test blocked domains."""
    blocked_urls = ["http://localhost/path", "https://127.0.0.1/", "http://0.0.0.0/"]

    for url in blocked_urls:
        with pytest.raises(ValidationError, match="URL domain not allowed"):
            validate_url(url)


def test_suspicious_url_content() -> None:
    """Test suspicious URL content."""
    suspicious_urls = [
        "https://example.com/javascript:alert()",
        "https://example.com/data:something",
        "https://example.com/vbscript:code",
    ]

    for url in suspicious_urls:
        with pytest.raises(ValidationError, match="URL contains suspicious content"):
            validate_url(url)


def test_url_too_long() -> None:
    """Test URL length limit."""
    long_url = "https://example.com/" + "a" * 2100
    with pytest.raises(ValidationError, match="URL too long"):
        validate_url(long_url)


def test_non_string_url() -> None:
    """Test non-string URL input."""
    with pytest.raises(ValidationError, match="URL must be a string"):
        validate_url(123)  # type: ignore[arg-type]


# Slug validation tests
def test_valid_slugs() -> None:
    """Test valid slugs."""
    valid_slugs = ["my-slug", "another-slug-123", "simple", "slug-with-numbers-123", "a"]

    for slug in valid_slugs:
        result = validate_slug(slug)
        assert result == slug


def test_invalid_slug_characters() -> None:
    """Test invalid characters in slugs."""
    invalid_slugs = [
        "My Slug",  # Space
        "slug_with_underscores",  # Underscore
        "slug.with.dots",  # Dots
        "slug@with@symbols",  # Symbols
    ]

    for slug in invalid_slugs:
        with pytest.raises(ValidationError, match="Slug can only contain"):
            validate_slug(slug)

    # Test that UPPERCASE gets converted
    result = validate_slug("UPPERCASE")
    assert result == "uppercase"


def test_slug_hyphen_rules() -> None:
    """Test slug hyphen placement rules."""
    invalid_slugs = ["-starts-with-hyphen", "ends-with-hyphen-", "has--double-hyphens"]

    for slug in invalid_slugs:
        with pytest.raises(ValidationError):
            validate_slug(slug)


def test_slug_length_limits() -> None:
    """Test slug length validation."""
    # Empty slug
    with pytest.raises(ValidationError, match="Slug cannot be empty"):
        validate_slug("")

    # Too long slug
    long_slug = "a" * 101
    with pytest.raises(ValidationError, match="Slug must not exceed"):
        validate_slug(long_slug)


def test_slug_case_normalization() -> None:
    """Test slug case normalization."""
    result = validate_slug("My-Slug")
    assert result == "my-slug"


def test_non_string_slug() -> None:
    """Test non-string slug input."""
    with pytest.raises(ValidationError, match="Slug must be a string"):
        validate_slug(123)  # type: ignore[arg-type]


# Helper validation function tests
def test_validate_not_empty() -> None:
    """Test not empty validation."""
    # Valid case
    result = validate_not_empty("  test  ")
    assert result == "test"

    # Invalid case
    with pytest.raises(ValidationError, match="Value cannot be empty"):
        validate_not_empty("   ")


def test_validate_length() -> None:
    """Test length validation."""
    # Valid case
    result = validate_length("test", min_length=2, max_length=10)
    assert result == "test"

    # Too short
    with pytest.raises(ValidationError, match="Must be at least"):
        validate_length("a", min_length=2)

    # Too long
    with pytest.raises(ValidationError, match="Must not exceed"):
        validate_length("toolong", max_length=5)


def test_validate_no_control_chars() -> None:
    """Test control character validation."""
    # Valid case
    result = validate_no_control_chars("normal text\n\r\t")
    assert result == "normal text\n\r\t"

    # Invalid case (null character)
    with pytest.raises(ValidationError, match="Contains invalid control characters"):
        validate_no_control_chars("text\x00with\x01control")
