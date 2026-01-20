"""Password validation and management service."""

from __future__ import annotations

import hashlib
import re
import secrets
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any

from sqlspec import sql

from sqlstack.domain.accounts import schemas as s
from sqlstack.domain.accounts.schemas._password import PasswordStrengthAnalysis
from sqlstack.lib.exceptions import ClientError
from sqlstack.lib.service import OffsetPagination, SQLSpecAsyncService, StatementFilter

if TYPE_CHECKING:
    from uuid import UUID

__all__ = ("PasswordService", "PasswordValidationError")

# Password patterns
PASSWORD_UPPERCASE_PATTERN = re.compile(r"[A-Z]")
PASSWORD_LOWERCASE_PATTERN = re.compile(r"[a-z]")
PASSWORD_DIGIT_PATTERN = re.compile(r"\d")
PASSWORD_SPECIAL_PATTERN = re.compile(r'[!@#$%^&*(),.?":{}|<>_+=\-\[\]\\\/~`]')
PASSWORD_COMMON_PATTERN = re.compile(r"(password|123456|qwerty|admin)", re.IGNORECASE)
PASSWORD_REPEATED_PATTERN = re.compile(r"(.)\1{4,}")  # 5+ repeated characters
PASSWORD_SIMPLE_REPEATED_PATTERN = re.compile(r"^(.)\1{11,}$")  # 12+ same character
PASSWORD_SEQUENTIAL_PATTERN = re.compile(r"^(012|123|234|345|456|567|678|789|890|abc|bcd|cde)", re.IGNORECASE)
PASSWORD_KEYBOARD_PATTERN = re.compile(r"^(qwe|asd|zxc)", re.IGNORECASE)

# Password length constants
PASSWORD_MIN_LENGTH = 12
PASSWORD_MAX_LENGTH = 128
PASSWORD_STRONG_LENGTH = 16
PASSWORD_VERY_STRONG_LENGTH = 20

# Password strength score thresholds
PASSWORD_SCORE_STRONG = 7
PASSWORD_SCORE_MEDIUM = 5

# Common passwords
COMMON_PASSWORDS = {
    "password",
    "password123",
    "123456789",
    "qwertyuiop",
    "administrator",
    "welcome123",
    "password1234",
    "letmein123",
    "admin123456",
    "password12345",
}

# Common passwords hash set (SHA256 hashes of most common passwords)
COMMON_PASSWORDS_HASHES = {
    # SHA256 hashes of common passwords
    "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",  # empty
    "5e884898da28047151d0e56f8dc6292773603d0d6aabbdd62a11ef721d1542d8",  # 'password'
    "65e84be33532fb784c48129675f9eff3a682b27168c0ea744b2cf58ee02337c5",  # 'qwerty'
    "8d969eef6ecad3c29a3a629280e686cf0c3f5d5a86aff3ca12020c923adc6c92",  # '123456'
    "15e2b0d3c33891ebb0f1ef609ec419420c20e320ce94c65fbc8c3312448eb225",  # '123456789'
    "a665a45920422f9d417e4867efdc4fb8a04a1f3fff1fa07e998e86f7f7a27ae3",  # '123'
    "9af15b336e6a9619928537df30b2e6a2376569fcf9d7e773eccede65606529a0",  # 'qwerty123'
    "0b14d501a594442a01c6859541bcb3e8164d183d32937b851835442f69d5c94e",  # 'password1'
    "e606e38b0d8c19b24cf0ee3808183162ea7cd63ff7912dbb22b5e803286b4446",  # 'password123'
    "c775e7b757ede630cd0aa1113bd102661ab38829ca52a6422ab782862f268646",  # '1234567890'
}


class PasswordValidationError(ClientError):
    """Exception raised when password validation fails."""


class PasswordService(SQLSpecAsyncService):
    """Service for password validation and management operations."""

    # Maximum password reset requests per hour
    MAX_RESET_REQUESTS_PER_HOUR = 3

    def validate_password_strength(self, password: str) -> None:
        """Validate password meets production security requirements.

        Args:
            password: The password to validate

        Raises:
            PasswordValidationError: If password doesn't meet requirements
        """
        if not isinstance(password, str):  # pyright: ignore
            msg = "Password must be a string"  # type: ignore[unreachable]
            raise PasswordValidationError(msg)

        # Length requirements
        if len(password) < PASSWORD_MIN_LENGTH:
            msg = f"Password must be at least {PASSWORD_MIN_LENGTH} characters long"
            raise PasswordValidationError(msg)

        if len(password) > PASSWORD_MAX_LENGTH:
            msg = f"Password must not exceed {PASSWORD_MAX_LENGTH} characters"
            raise PasswordValidationError(msg)

        # Character type requirements
        if not PASSWORD_UPPERCASE_PATTERN.search(password):
            msg = "Password must contain at least one uppercase letter"
            raise PasswordValidationError(msg)

        if not PASSWORD_LOWERCASE_PATTERN.search(password):
            msg = "Password must contain at least one lowercase letter"
            raise PasswordValidationError(msg)

        if not PASSWORD_DIGIT_PATTERN.search(password):
            msg = "Password must contain at least one digit"
            raise PasswordValidationError(msg)

        if not PASSWORD_SPECIAL_PATTERN.search(password):
            msg = "Password must contain at least one special character"
            raise PasswordValidationError(msg)

        # Check against common patterns
        if self._is_common_password(password):
            msg = "Password is too common - please choose a more unique password"
            raise PasswordValidationError(msg)

    def _is_common_password(self, password: str) -> bool:
        """Check if password is in common password list.

        Args:
            password: The password to check

        Returns:
            True if password is common, False otherwise
        """
        password_lower = password.lower()

        # Check exact matches
        if password_lower in COMMON_PASSWORDS:
            return True

        # Check for simple patterns
        if PASSWORD_SIMPLE_REPEATED_PATTERN.match(password):  # Repeated characters
            return True

        if PASSWORD_SEQUENTIAL_PATTERN.match(password_lower):
            return True

        return bool(PASSWORD_KEYBOARD_PATTERN.match(password_lower))

    def get_password_strength(self, password: str) -> PasswordStrengthAnalysis:
        """Get detailed password strength analysis.

        Args:
            password: The password to analyze

        Returns:
            PasswordStrengthAnalysis with strength details
        """
        analysis_data: dict[str, Any] = {
            "score": 0,
            "strength": "weak",
            "requirements": {
                "length": len(password) >= PASSWORD_MIN_LENGTH,
                "uppercase": bool(PASSWORD_UPPERCASE_PATTERN.search(password)),
                "lowercase": bool(PASSWORD_LOWERCASE_PATTERN.search(password)),
                "digits": bool(PASSWORD_DIGIT_PATTERN.search(password)),
                "special_chars": bool(PASSWORD_SPECIAL_PATTERN.search(password)),
                "not_common": not self._is_common_password(password),
            },
            "feedback": [],
        }

        # Calculate score
        if analysis_data["requirements"]["length"]:
            analysis_data["score"] += 2
        else:
            analysis_data["feedback"].append("Use at least 12 characters")

        if analysis_data["requirements"]["uppercase"]:
            analysis_data["score"] += 1
        else:
            analysis_data["feedback"].append("Include uppercase letters")

        if analysis_data["requirements"]["lowercase"]:
            analysis_data["score"] += 1
        else:
            analysis_data["feedback"].append("Include lowercase letters")

        if analysis_data["requirements"]["digits"]:
            analysis_data["score"] += 1
        else:
            analysis_data["feedback"].append("Include numbers")

        if analysis_data["requirements"]["special_chars"]:
            analysis_data["score"] += 1
        else:
            analysis_data["feedback"].append("Include special characters (!@#$%^&*)")

        if analysis_data["requirements"]["not_common"]:
            analysis_data["score"] += 1
        else:
            analysis_data["feedback"].append("Avoid common passwords")

        # Bonus points for length
        if len(password) >= PASSWORD_STRONG_LENGTH:
            analysis_data["score"] += 1
        if len(password) >= PASSWORD_VERY_STRONG_LENGTH:
            analysis_data["score"] += 1

        # Determine strength level
        if analysis_data["score"] >= PASSWORD_SCORE_STRONG:
            analysis_data["strength"] = "strong"
        elif analysis_data["score"] >= PASSWORD_SCORE_MEDIUM:
            analysis_data["strength"] = "medium"
        else:
            analysis_data["strength"] = "weak"

        return PasswordStrengthAnalysis(**analysis_data)

    def validate_password(self, password: str) -> str:
        """Production-ready password validation with security checks.

        Args:
            password: The password to validate

        Returns:
            The validated password

        Raises:
            PasswordValidationError: If password doesn't meet requirements
        """
        if not isinstance(password, str):  # pyright: ignore
            msg = "Password must be a string"  # type: ignore[unreachable]
            raise PasswordValidationError(msg)

        # Use existing validation function
        self.validate_password_strength(password)

        # Check against common passwords
        password_hash = hashlib.sha256(password.encode()).hexdigest()
        if password_hash in COMMON_PASSWORDS_HASHES:
            msg = "Password is too common, please choose a different one"
            raise PasswordValidationError(msg)

        return password

    def generate_secure_token(self, length: int = 32) -> str:
        """Generate a cryptographically secure token.

        Args:
            length: Length of the token in bytes

        Returns:
            Hex-encoded secure token
        """
        return secrets.token_hex(length)

    # Password Reset Token Management

    async def create_reset_token(self, user_id: UUID) -> s.PasswordResetToken:
        """Create a new password reset token for a user.

        Invalidates any existing tokens for the user before creating a new one.

        Args:
            user_id: The ID of the user requesting password reset

        Returns:
            The created password reset token
        """
        await self._check_rate_limit(user_id)
        await self.invalidate_user_tokens(user_id)
        return await self.driver.select_one(
            sql
            .insert("password_reset_token")
            .values(
                user_id=user_id,
                token=secrets.token_urlsafe(32),
                expires_at=datetime.now(UTC) + timedelta(hours=1),
                used=False,
            )
            .returning("id", "user_id", "token", "expires_at", "used"),
            schema_type=s.PasswordResetToken,
        )

    async def validate_reset_token(self, token: str) -> s.PasswordResetToken:
        """Validate a password reset token without consuming it.

        Args:
            token: The reset token to validate

        Returns:
            The token record if valid

        Raises:
            ValueError: If token is invalid, expired, or already used
        """
        token_record = await self.driver.select_one_or_none(
            sql
            .select("id", "user_id", "token", "expires_at", "used")
            .from_("password_reset_token")
            .where_eq("token", token)
            .where_eq("used", False),
            schema_type=s.PasswordResetToken,
        )

        if not token_record:
            msg = "Invalid or already used reset token"
            raise ValueError(msg)

        if datetime.now(UTC) > token_record.expires_at:
            msg = "Reset token has expired"
            raise ValueError(msg)

        return token_record

    async def use_reset_token(self, token: str) -> s.PasswordResetToken:
        """Mark a reset token as used after successful password reset.

        Args:
            token: The reset token to mark as used

        Returns:
            The updated token record
        """
        token_record = await self.validate_reset_token(token)
        await self.driver.execute(
            sql
            .update("password_reset_token")
            .set(used=True, updated_at=sql.raw("NOW()"))
            .where_eq("id", token_record.id)
        )
        return await self.driver.select_one(
            sql
            .select("id", "user_id", "token", "expires_at", "used")
            .from_("password_reset_token")
            .where_eq("id", token_record.id),
            schema_type=s.PasswordResetToken,
        )

    async def invalidate_user_tokens(self, user_id: UUID) -> None:
        """Mark all existing reset tokens for a user as used."""
        await self.driver.execute(
            sql
            .update("password_reset_token")
            .set(used=True, updated_at=sql.raw("NOW()"))
            .where_eq("user_id", user_id)
            .where_eq("used", False)
        )

    async def cleanup_expired_tokens(self) -> int:
        """Remove expired reset tokens and return count of deleted records."""
        result = await self.driver.execute(sql.delete("password_reset_token").where_lt("expires_at", sql.raw("NOW()")))
        return result.rows_affected

    async def _check_rate_limit(self, user_id: UUID) -> None:
        """Check if user has exceeded the rate limit for password reset requests.

        Allows maximum 3 requests per hour.

        Args:
            user_id: The ID of the user to check

        Raises:
            ValueError: If rate limit is exceeded
        """
        one_hour_ago = datetime.now(UTC) - timedelta(hours=1)
        token_count = await self.driver.select_value(
            sql
            .select("COUNT(1) as count")
            .from_("password_reset_token")
            .where_eq("user_id", user_id)
            .where_gte("created_at", one_hour_ago)
        )
        if token_count >= self.MAX_RESET_REQUESTS_PER_HOUR:
            msg = f"Rate limit exceeded. Maximum {self.MAX_RESET_REQUESTS_PER_HOUR} password reset requests per hour."
            raise ValueError(msg)

    async def get_user_token_count(self, user_id: UUID, hours: int = 1) -> int:
        """Get the number of reset tokens created for a user in the specified time period."""
        time_ago = datetime.now(UTC) - timedelta(hours=hours)
        token_count = await self.driver.select_value(
            sql
            .select("COUNT(1) as count")
            .from_("password_reset_token")
            .where_eq("user_id", user_id)
            .where_gte("created_at", time_ago)
        )
        return int(token_count)

    async def get_pending_tokens_for_user(self, user_id: UUID) -> list[s.PasswordResetToken]:
        """Get all active (non-expired, non-used) reset tokens for a user."""
        return await self.driver.select(
            sql
            .select("id", "user_id", "token", "expires_at", "used")
            .from_("password_reset_token")
            .where_eq("user_id", user_id)
            .where_eq("used", False)
            .where_gte("expires_at", sql.raw("NOW()"))
            .order_by(sql.column("created_at").desc()),
            schema_type=s.PasswordResetToken,
        )

    async def has_valid_token(self, user_id: UUID) -> bool:
        """Check if user has any valid (non-expired, non-used) reset tokens."""
        result = await self.driver.select_one_or_none(
            sql
            .select("1")
            .from_("password_reset_token")
            .where_eq("user_id", user_id)
            .where_eq("used", False)
            .where_gte("expires_at", sql.raw("NOW()"))
        )
        return result is not None

    async def list_tokens(self, *filters: StatementFilter) -> OffsetPagination[s.PasswordResetToken]:
        """List password reset tokens with pagination."""
        return await self.paginate(
            sql
            .select("id", "user_id", "token", "expires_at", "used")
            .from_("password_reset_token")
            .order_by(sql.column("created_at").desc()),
            *filters,
            schema_type=s.PasswordResetToken,
        )

    async def get_token_by_value(self, token: str) -> s.PasswordResetToken | None:
        """Get a reset token by its value."""
        return await self.driver.select_one_or_none(
            sql
            .select("id", "user_id", "token", "expires_at", "used")
            .from_("password_reset_token")
            .where_eq("token", token),
            schema_type=s.PasswordResetToken,
        )

    async def get_token_statistics(self) -> dict[str, Any]:
        """Get statistics about password reset tokens."""
        return await self.driver.select_one(
            sql.select(
                "COUNT(*) as total_tokens",
                "COUNT(CASE WHEN used = true THEN 1 END) as used_tokens",
                "COUNT(CASE WHEN used = false AND expires_at > NOW() THEN 1 END) as active_tokens",
                "COUNT(CASE WHEN used = false AND expires_at <= NOW() THEN 1 END) as expired_tokens",
            ).from_("password_reset_token")
        )
