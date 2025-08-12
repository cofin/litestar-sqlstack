"""Unit tests for validation utilities."""

from __future__ import annotations

import pytest

from sqlstack.lib.validation import (
    PASSWORD_MIN_LENGTH,
    PASSWORD_SCORE_MEDIUM,
    PASSWORD_SCORE_STRONG,
    PasswordValidationError,
    ValidationError,
    get_password_strength,
    validate_email,
    validate_name,
    validate_password,
    validate_password_strength,
    validate_phone,
    validate_slug,
    validate_url,
    validate_username,
)


class TestEmailValidation:
    """Test email validation."""

    def test_valid_emails(self) -> None:
        """Test valid email addresses."""
        valid_emails = [
            "user@example.com",
            "user.email@domain.org",  # Changed from "test.email"
            "user+tag@example.co.uk",
            "firstname.lastname@company.com",
            "a@b.co",
            "user123@example.com",  # Changed from "123@example.com"
        ]
        
        for email in valid_emails:
            result = validate_email(email)
            assert result == email.lower()

    def test_invalid_email_formats(self) -> None:
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

    def test_blocked_domains(self) -> None:
        """Test blocked email domains."""
        blocked_emails = [
            "user@10minutemail.com",
            "test@tempmail.org",
            "fake@guerrillamail.com",
        ]
        
        for email in blocked_emails:
            with pytest.raises(ValidationError, match="Email domain not allowed"):
                validate_email(email)

    def test_blocked_patterns(self) -> None:
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

    def test_email_length_limits(self) -> None:
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

    def test_email_case_normalization(self) -> None:
        """Test email case normalization."""
        result = validate_email("USER@EXAMPLE.COM")
        assert result == "user@example.com"

    def test_non_string_email(self) -> None:
        """Test non-string email input."""
        with pytest.raises(ValidationError, match="Email must be a string"):
            validate_email(123)  # type: ignore[arg-type]


class TestPasswordValidation:
    """Test password validation."""

    def test_valid_passwords(self) -> None:
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

    def test_password_too_short(self) -> None:
        """Test password too short."""
        short_password = "Short1!"
        with pytest.raises(PasswordValidationError, match=f"Password must be at least {PASSWORD_MIN_LENGTH} characters long"):
            validate_password_strength(short_password)

    def test_password_too_long(self) -> None:
        """Test password too long."""
        long_password = "a" * 200
        with pytest.raises(PasswordValidationError, match="Password must not exceed"):
            validate_password_strength(long_password)

    def test_password_missing_uppercase(self) -> None:
        """Test password missing uppercase letter."""
        with pytest.raises(PasswordValidationError, match="Password must contain at least one uppercase letter"):
            validate_password_strength("mysecurepassword123!")

    def test_password_missing_lowercase(self) -> None:
        """Test password missing lowercase letter."""
        with pytest.raises(PasswordValidationError, match="Password must contain at least one lowercase letter"):
            validate_password_strength("MYSECUREPASSWORD123!")

    def test_password_missing_digit(self) -> None:
        """Test password missing digit."""
        with pytest.raises(PasswordValidationError, match="Password must contain at least one digit"):
            validate_password_strength("MySecurePassword!")

    def test_password_missing_special_char(self) -> None:
        """Test password missing special character."""
        with pytest.raises(PasswordValidationError, match="Password must contain at least one special character"):
            validate_password_strength("MySecurePassword123")

    def test_common_passwords(self) -> None:
        """Test common password detection."""
        # Test exact matches from COMMON_PASSWORDS set that meet requirements
        # We need to check which ones are actually in the set and build valid versions
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

    def test_repeated_character_patterns(self) -> None:
        """Test repeated character patterns."""
        with pytest.raises(PasswordValidationError, match="Password is too common"):
            validate_password_strength("Aaaaaaaaaaaaa1!")  # 13+ same character but meets basic requirements

    def test_sequential_patterns(self) -> None:
        """Test sequential patterns."""
        sequential_passwords = [
            "123456789012A!",  # Sequential but with required chars
            "Abcdefghijkl1!",  # Sequential but with required chars  
            "Qwertyuiopas1!",  # Sequential but with required chars
        ]
        
        for password in sequential_passwords:
            with pytest.raises(PasswordValidationError, match="Password is too common"):
                validate_password_strength(password)

    def test_non_string_password(self) -> None:
        """Test non-string password input."""
        with pytest.raises(PasswordValidationError, match="Password must be a string"):
            validate_password_strength(123)  # type: ignore[arg-type]


class TestPasswordStrength:
    """Test password strength analysis."""

    def test_weak_password_analysis(self) -> None:
        """Test weak password analysis."""
        analysis = get_password_strength("weak")
        
        assert analysis["strength"] == "weak"
        assert analysis["score"] < PASSWORD_SCORE_MEDIUM
        assert len(analysis["feedback"]) > 0

    def test_medium_password_analysis(self) -> None:
        """Test medium strength password."""
        analysis = get_password_strength("MediumPass123!")
        
        assert analysis["strength"] in ["medium", "strong"]
        assert analysis["score"] >= PASSWORD_SCORE_MEDIUM

    def test_strong_password_analysis(self) -> None:
        """Test strong password analysis."""
        analysis = get_password_strength("VeryStrongPassword123!@#$%")
        
        assert analysis["strength"] == "strong"
        assert analysis["score"] >= PASSWORD_SCORE_STRONG

    def test_password_requirements_check(self) -> None:
        """Test password requirements checking."""
        analysis = get_password_strength("TestPassword123!")
        
        assert analysis["requirements"]["length"] is True
        assert analysis["requirements"]["uppercase"] is True
        assert analysis["requirements"]["lowercase"] is True
        assert analysis["requirements"]["digits"] is True
        assert analysis["requirements"]["special_chars"] is True

    def test_password_feedback_generation(self) -> None:
        """Test feedback generation for weak passwords."""
        analysis = get_password_strength("weak")
        
        assert isinstance(analysis["feedback"], list)
        assert len(analysis["feedback"]) > 0
        assert any("characters" in feedback for feedback in analysis["feedback"])


class TestNameValidation:
    """Test name validation."""

    def test_valid_names(self) -> None:
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

    def test_invalid_name_characters(self) -> None:
        """Test invalid characters in names."""
        invalid_names = [
            "John123",  # Numbers
            "Jane@Doe",  # @ symbol
            "User<script>",  # HTML
            "Name\n\r",  # Control characters
        ]
        
        for name in invalid_names:
            with pytest.raises(ValidationError):
                validate_name(name)

    def test_name_length_limits(self) -> None:
        """Test name length validation."""
        # Empty name
        with pytest.raises(ValidationError, match="Name cannot be empty"):
            validate_name("")

        # Too long name
        long_name = "a" * 101
        with pytest.raises(ValidationError, match="Name must not exceed"):
            validate_name(long_name)

    def test_name_whitespace_normalization(self) -> None:
        """Test name whitespace normalization."""
        result = validate_name("  John    Doe  ")
        assert result == "John Doe"

    def test_repeated_character_abuse(self) -> None:
        """Test repeated character abuse detection."""
        with pytest.raises(ValidationError, match="Name contains suspicious patterns"):
            validate_name("Johnnnnnnnn")

    def test_non_string_name(self) -> None:
        """Test non-string name input."""
        with pytest.raises(ValidationError, match="Name must be a string"):
            validate_name(123)  # type: ignore[arg-type]


class TestUsernameValidation:
    """Test username validation."""

    def test_valid_usernames(self) -> None:
        """Test valid usernames."""
        valid_usernames = [
            "john_doe",
            "user123",
            "test-user",
            "user_name_123",
            "a1b2c3",
        ]
        
        for username in valid_usernames:
            result = validate_username(username)
            assert result == username.lower()

    def test_invalid_username_characters(self) -> None:
        """Test invalid characters in usernames."""
        invalid_usernames = [
            "John Doe",  # Space
            "user@name",  # @ symbol
            "user.name",  # Dot
            "user!name",  # Special character
            # Note: UPPERCASE gets lowercased so it's actually valid
        ]
        
        for username in invalid_usernames:
            with pytest.raises(ValidationError, match="Username can only contain"):
                validate_username(username)
                
        # Test that UPPERCASE gets converted
        result = validate_username("UPPERCASE")
        assert result == "uppercase"

    def test_username_length_limits(self) -> None:
        """Test username length validation."""
        # Too short
        with pytest.raises(ValidationError, match="Username must be at least"):
            validate_username("ab")

        # Too long
        long_username = "a" * 31
        with pytest.raises(ValidationError, match="Username must not exceed"):
            validate_username(long_username)

    def test_username_start_character(self) -> None:
        """Test username must start with letter or number."""
        invalid_starts = ["_username", "-username"]
        
        for username in invalid_starts:
            with pytest.raises(ValidationError, match="Username must start with a letter or number"):
                validate_username(username)

    def test_reserved_usernames(self) -> None:
        """Test reserved username blocking."""
        reserved_usernames = ["admin", "root", "api", "www", "support"]
        
        for username in reserved_usernames:
            with pytest.raises(ValidationError, match="Username is reserved"):
                validate_username(username)

    def test_username_repeated_characters(self) -> None:
        """Test repeated character abuse detection."""
        with pytest.raises(ValidationError, match="Username contains too many repeated characters"):
            validate_username("userrrrrr")

    def test_username_case_normalization(self) -> None:
        """Test username case normalization."""
        result = validate_username("UserName")
        assert result == "username"

    def test_non_string_username(self) -> None:
        """Test non-string username input."""
        with pytest.raises(ValidationError, match="Username must be a string"):
            validate_username(123)  # type: ignore[arg-type]


class TestUrlValidation:
    """Test URL validation."""

    def test_valid_urls(self) -> None:
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

    def test_invalid_url_schemes(self) -> None:
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

    def test_missing_scheme(self) -> None:
        """Test URLs without scheme."""
        with pytest.raises(ValidationError, match="URL must include a scheme"):
            validate_url("example.com")

    def test_missing_hostname(self) -> None:
        """Test URLs without hostname."""
        with pytest.raises(ValidationError, match="URL must include a hostname"):
            validate_url("https://")

    def test_blocked_domains(self) -> None:
        """Test blocked domains."""
        blocked_urls = [
            "http://localhost/path",
            "https://127.0.0.1/",
            "http://0.0.0.0/",
        ]
        
        for url in blocked_urls:
            with pytest.raises(ValidationError, match="URL domain not allowed"):
                validate_url(url)

    def test_suspicious_content(self) -> None:
        """Test suspicious URL content."""
        suspicious_urls = [
            "https://example.com/javascript:alert()",
            "https://example.com/data:something",
            "https://example.com/vbscript:code",
        ]
        
        for url in suspicious_urls:
            with pytest.raises(ValidationError, match="URL contains suspicious content"):
                validate_url(url)

    def test_url_too_long(self) -> None:
        """Test URL length limit."""
        long_url = "https://example.com/" + "a" * 2100
        with pytest.raises(ValidationError, match="URL too long"):
            validate_url(long_url)

    def test_non_string_url(self) -> None:
        """Test non-string URL input."""
        with pytest.raises(ValidationError, match="URL must be a string"):
            validate_url(123)  # type: ignore[arg-type]


class TestSlugValidation:
    """Test slug validation."""

    def test_valid_slugs(self) -> None:
        """Test valid slugs."""
        valid_slugs = [
            "my-slug",
            "another-slug-123",
            "simple",
            "slug-with-numbers-123",
            "a",
        ]
        
        for slug in valid_slugs:
            result = validate_slug(slug)
            assert result == slug

    def test_invalid_slug_characters(self) -> None:
        """Test invalid characters in slugs."""
        invalid_slugs = [
            "My Slug",  # Space
            "slug_with_underscores",  # Underscore
            "slug.with.dots",  # Dots
            "slug@with@symbols",  # Symbols
            # Note: UPPERCASE will be converted to lowercase, so it's actually valid
        ]
        
        for slug in invalid_slugs:
            with pytest.raises(ValidationError, match="Slug can only contain"):
                validate_slug(slug)
                
        # Test that UPPERCASE gets converted
        result = validate_slug("UPPERCASE")
        assert result == "uppercase"

    def test_slug_hyphen_rules(self) -> None:
        """Test slug hyphen placement rules."""
        invalid_slugs = [
            "-starts-with-hyphen",
            "ends-with-hyphen-",
            "has--double-hyphens",
        ]
        
        for slug in invalid_slugs:
            with pytest.raises(ValidationError):
                validate_slug(slug)

    def test_slug_length_limits(self) -> None:
        """Test slug length validation."""
        # Empty slug
        with pytest.raises(ValidationError, match="Slug cannot be empty"):
            validate_slug("")

        # Too long slug
        long_slug = "a" * 101
        with pytest.raises(ValidationError, match="Slug must not exceed"):
            validate_slug(long_slug)

    def test_slug_case_normalization(self) -> None:
        """Test slug case normalization."""
        result = validate_slug("My-Slug")
        assert result == "my-slug"

    def test_non_string_slug(self) -> None:
        """Test non-string slug input."""
        with pytest.raises(ValidationError, match="Slug must be a string"):
            validate_slug(123)  # type: ignore[arg-type]


class TestPhoneValidation:
    """Test phone number validation."""

    def test_valid_phone_numbers(self) -> None:
        """Test valid phone numbers."""
        valid_phones = [
            "+1234567890",
            "(555) 123-4567",
            "555.123.4567",
            "+44 20 7946 0958",
            "1234567890",
            "+1 (555) 123-4567",
        ]
        
        for phone in valid_phones:
            result = validate_phone(phone)
            assert result == phone

    def test_invalid_phone_characters(self) -> None:
        """Test invalid characters in phone numbers."""
        invalid_phones = [
            "123-456-789a",  # Letter
            "555-123-4567#123",  # Hash
            "phone-number",  # Text
            "123@456.7890",  # @ symbol
        ]
        
        for phone in invalid_phones:
            with pytest.raises(ValidationError, match="Invalid phone number format"):
                validate_phone(phone)

    def test_phone_length_limits(self) -> None:
        """Test phone number length validation."""
        # Too short
        with pytest.raises(ValidationError, match="Phone number must be between"):
            validate_phone("123456")

        # Too long
        with pytest.raises(ValidationError, match="Phone number must be between"):
            validate_phone("1234567890123456")

    def test_empty_phone(self) -> None:
        """Test empty phone number."""
        with pytest.raises(ValidationError, match="Phone number cannot be empty"):
            validate_phone("")

    def test_non_string_phone(self) -> None:
        """Test non-string phone input."""
        with pytest.raises(ValidationError, match="Phone number must be a string"):
            validate_phone(123456789)  # type: ignore[arg-type]


class TestValidationHelpers:
    """Test helper validation functions."""

    def test_validate_not_empty(self) -> None:
        """Test not empty validation."""
        from sqlstack.lib.validation import validate_not_empty
        
        # Valid case
        result = validate_not_empty("  test  ")
        assert result == "test"
        
        # Invalid case
        with pytest.raises(ValidationError, match="Value cannot be empty"):
            validate_not_empty("   ")

    def test_validate_length(self) -> None:
        """Test length validation."""
        from sqlstack.lib.validation import validate_length
        
        # Valid case
        result = validate_length("test", min_length=2, max_length=10)
        assert result == "test"
        
        # Too short
        with pytest.raises(ValidationError, match="Must be at least"):
            validate_length("a", min_length=2)
        
        # Too long
        with pytest.raises(ValidationError, match="Must not exceed"):
            validate_length("toolong", max_length=5)

    def test_validate_no_control_chars(self) -> None:
        """Test control character validation."""
        from sqlstack.lib.validation import validate_no_control_chars
        
        # Valid case
        result = validate_no_control_chars("normal text\n\r\t")
        assert result == "normal text\n\r\t"
        
        # Invalid case (null character)
        with pytest.raises(ValidationError, match="Contains invalid control characters"):
            validate_no_control_chars("text\x00with\x01control")