from __future__ import annotations

import secrets
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

from sqlspec import sql

from sqlstack import schemas as s
from sqlstack.services._base import OffsetPagination, SQLSpecService, StatementFilter

if TYPE_CHECKING:
    from uuid import UUID

__all__ = ["EmailVerificationService"]


class EmailVerificationService(SQLSpecService):
    """Handles database operations for email verification tokens and processes."""

    async def create_verification_token(self, user_id: UUID, email: str) -> s.EmailVerificationToken:
        """Create a new email verification token for a user.

        Invalidates any existing tokens for the user before creating a new one.
        """
        # Invalidate existing tokens for this user
        await self.invalidate_user_tokens(user_id)

        return await self.driver.select_one(
            sql.insert("email_verification_token")
            .values(
                user_id=user_id,
                email=email,
                token=secrets.token_urlsafe(32),
                expires_at=datetime.now(UTC) + timedelta(hours=24),
                used=False,
            )
            .returning("id", "user_id", "email", "token", "expires_at", "used", "created_at", "updated_at"),
            schema_type=s.EmailVerificationToken,
        )

    async def verify_token(self, token: str) -> s.User:
        """Verify an email verification token and mark user as verified.

        Raises:
            ValueError: If token is invalid, expired, or already used
        """
        # Get token details
        token_record = await self.driver.select_one_or_none(
            sql.select("id", "user_id", "email", "token", "expires_at", "used", "created_at", "updated_at")
            .from_("email_verification_token")
            .where_eq("token", token)
            .where_eq("used", False),
            schema_type=s.EmailVerificationToken,
        )

        if not token_record:
            msg = "Invalid or already used verification token"
            raise ValueError(msg)

        # Check if token is expired
        if datetime.now(UTC) > token_record.expires_at:
            msg = "Verification token has expired"
            raise ValueError(msg)

        # Mark token as used
        await self.driver.execute(
            sql.update("email_verification_token")
            .set(used=True, updated_at=sql.raw("NOW()"))
            .where_eq("id", token_record.id),
        )

        # Update user as verified
        return await self.driver.select_one(
            sql.update("user_account")
            .set(is_verified=True, updated_at=sql.raw("NOW()"))
            .where_eq("id", token_record.user_id)
            .returning(
                "id",
                "email",
                "name",
                "is_superuser",
                "is_active",
                "is_verified",
                "password_hash",
                "avatar_url",
                "created_at",
                "updated_at",
                "last_login",
            ),
            schema_type=s.User,
        )

    async def invalidate_user_tokens(self, user_id: UUID) -> None:
        """Mark all existing verification tokens for a user as used."""
        await self.driver.execute(
            sql.update("email_verification_token")
            .set(used=True, updated_at=sql.raw("NOW()"))
            .where_eq("user_id", user_id)
            .where_eq("used", False),
        )

    async def cleanup_expired_tokens(self) -> int:
        """Remove expired verification tokens and return count of deleted records."""
        result = await self.driver.execute(
            sql.delete("email_verification_token").where_lt("expires_at", sql.raw("NOW()")),
        )
        return result.get_affected_count()

    async def get_user_verification_status(self, user_id: UUID) -> bool:
        """Check if a user's email is verified."""
        result = await self.driver.select_one_or_none(
            sql.select("is_verified").from_("user_account").where_eq("id", user_id),
        )
        return result["is_verified"] if result else False

    async def get_pending_tokens_for_user(self, user_id: UUID) -> list[s.EmailVerificationToken]:
        """Get all active (non-expired, non-used) tokens for a user."""
        return await self.driver.select(
            sql.select("id", "user_id", "email", "token", "expires_at", "used", "created_at", "updated_at")
            .from_("email_verification_token")
            .where_eq("user_id", user_id)
            .where_eq("used", False)
            .where_gte("expires_at", sql.raw("NOW()"))
            .order_by(sql.column("created_at").desc()),
            schema_type=s.EmailVerificationToken,
        )

    async def has_valid_token(self, user_id: UUID) -> bool:
        """Check if user has any valid (non-expired, non-used) verification tokens."""
        result = await self.driver.select_one_or_none(
            sql.select("1")
            .from_("email_verification_token")
            .where_eq("user_id", user_id)
            .where_eq("used", False)
            .where_gte("expires_at", sql.raw("NOW()")),
        )
        return result is not None

    async def list_tokens(self, *filters: StatementFilter) -> OffsetPagination[s.EmailVerificationToken]:
        """List email verification tokens with pagination."""
        return await self.paginate(
            sql.select("id", "user_id", "email", "token", "expires_at", "used", "created_at", "updated_at")
            .from_("email_verification_token")
            .order_by(sql.column("created_at").desc()),
            *filters,
            schema_type=s.EmailVerificationToken,
        )

    async def get_token_by_value(self, token: str) -> s.EmailVerificationToken | None:
        """Get a verification token by its value."""
        return await self.driver.select_one_or_none(
            sql.select("id", "user_id", "email", "token", "expires_at", "used", "created_at", "updated_at")
            .from_("email_verification_token")
            .where_eq("token", token),
            schema_type=s.EmailVerificationToken,
        )
