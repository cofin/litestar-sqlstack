from __future__ import annotations

import secrets
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

from sqlspec import sql

from sqlstack import schemas as s
from sqlstack.services._base import OffsetPagination, SQLSpecService, StatementFilter

if TYPE_CHECKING:
    from uuid import UUID

__all__ = ["PasswordResetService"]


class PasswordResetService(SQLSpecService):
    """Handles database operations for password reset tokens and processes."""

    # Maximum password reset requests per hour
    MAX_RESET_REQUESTS_PER_HOUR = 3

    async def create_reset_token(self, user_id: UUID) -> s.PasswordResetToken:
        """Create a new password reset token for a user.

        Invalidates any existing tokens for the user before creating a new one.

        Args:
            user_id: The ID of the user requesting password reset

        Returns:
            The created password reset token

        Raises:
            ValueError: If rate limit is exceeded (more than 3 requests per hour)
        """
        # Check rate limiting
        await self._check_rate_limit(user_id)

        # Invalidate existing tokens for this user
        await self.invalidate_user_tokens(user_id)

        # Generate secure token
        token = secrets.token_urlsafe(32)
        expires_at = datetime.now(UTC) + timedelta(hours=1)  # 1 hour expiration

        token_data = {
            "user_id": user_id,
            "token": token,
            "expires_at": expires_at,
            "used": False,
        }

        return await self.driver.select_one(
            sql.insert("password_reset_token")
            .values(**token_data)
            .returning("id", "user_id", "token", "expires_at", "used", "created_at", "updated_at"),
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
            sql.select("id", "user_id", "token", "expires_at", "used", "created_at", "updated_at")
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

        Raises:
            ValueError: If token is invalid, expired, or already used
        """
        # First validate the token
        token_record = await self.validate_reset_token(token)

        # Mark token as used
        await self.driver.execute(
            sql.update("password_reset_token")
            .set(used=True, updated_at=sql.raw("NOW()"))
            .where_eq("id", token_record.id),
        )

        # Return updated record
        return await self.driver.select_one(
            sql.select("id", "user_id", "token", "expires_at", "used", "created_at", "updated_at")
            .from_("password_reset_token")
            .where_eq("id", token_record.id),
            schema_type=s.PasswordResetToken,
        )

    async def invalidate_user_tokens(self, user_id: UUID) -> None:
        """Mark all existing reset tokens for a user as used."""
        await self.driver.execute(
            sql.update("password_reset_token")
            .set(used=True, updated_at=sql.raw("NOW()"))
            .where_eq("user_id", user_id)
            .where_eq("used", False),
        )

    async def cleanup_expired_tokens(self) -> int:
        """Remove expired reset tokens and return count of deleted records."""
        result = await self.driver.execute(sql.delete("password_reset_token").where_lt("expires_at", sql.raw("NOW()")))
        return result.rowcount if hasattr(result, "rowcount") else 0

    async def _check_rate_limit(self, user_id: UUID) -> None:
        """Check if user has exceeded the rate limit for password reset requests.

        Allows maximum 3 requests per hour.

        Args:
            user_id: The ID of the user to check

        Raises:
            ValueError: If rate limit is exceeded
        """
        one_hour_ago = datetime.now(UTC) - timedelta(hours=1)

        # Count tokens created in the last hour
        result = await self.driver.select_one(
            sql.select("COUNT(*) as count")
            .from_("password_reset_token")
            .where_eq("user_id", user_id)
            .where_gte("created_at", one_hour_ago),
        )

        token_count = result["count"]
        if token_count >= self.MAX_RESET_REQUESTS_PER_HOUR:
            msg = f"Rate limit exceeded. Maximum {self.MAX_RESET_REQUESTS_PER_HOUR} password reset requests per hour."
            raise ValueError(msg)

    async def get_user_token_count(self, user_id: UUID, hours: int = 1) -> int:
        """Get the number of reset tokens created for a user in the specified time period."""
        time_ago = datetime.now(UTC) - timedelta(hours=hours)

        result = await self.driver.select_one(
            sql.select("COUNT(*) as count")
            .from_("password_reset_token")
            .where_eq("user_id", user_id)
            .where_gte("created_at", time_ago),
        )

        return int(result["count"])

    async def get_pending_tokens_for_user(self, user_id: UUID) -> list[s.PasswordResetToken]:
        """Get all active (non-expired, non-used) reset tokens for a user."""
        return await self.driver.select(
            sql.select("id", "user_id", "token", "expires_at", "used", "created_at", "updated_at")
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
            sql.select("1")
            .from_("password_reset_token")
            .where_eq("user_id", user_id)
            .where_eq("used", False)
            .where_gte("expires_at", sql.raw("NOW()")),
        )
        return result is not None

    async def list_tokens(self, *filters: StatementFilter) -> OffsetPagination[s.PasswordResetToken]:
        """List password reset tokens with pagination."""
        return await self.paginate(
            sql.select("id", "user_id", "token", "expires_at", "used", "created_at", "updated_at")
            .from_("password_reset_token")
            .order_by(sql.column("created_at").desc()),
            *filters,
            schema_type=s.PasswordResetToken,
        )

    async def get_token_by_value(self, token: str) -> s.PasswordResetToken | None:
        """Get a reset token by its value."""
        return await self.driver.select_one_or_none(
            sql.select("id", "user_id", "token", "expires_at", "used", "created_at", "updated_at")
            .from_("password_reset_token")
            .where_eq("token", token),
            schema_type=s.PasswordResetToken,
        )

    async def get_token_statistics(self) -> dict:
        """Get statistics about password reset tokens."""
        return await self.driver.select_one(
            sql.select(
                "COUNT(*) as total_tokens",
                "COUNT(CASE WHEN used = true THEN 1 END) as used_tokens",
                "COUNT(CASE WHEN used = false AND expires_at > NOW() THEN 1 END) as active_tokens",
                "COUNT(CASE WHEN used = false AND expires_at <= NOW() THEN 1 END) as expired_tokens",
            ).from_("password_reset_token"),
        )
