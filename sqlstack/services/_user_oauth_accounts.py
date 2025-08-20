from __future__ import annotations

from typing import TYPE_CHECKING, Any

from sqlspec import sql
from sqlspec.utils.type_guards import schema_dump

from sqlstack import schemas as s
from sqlstack.config import db_manager
from sqlstack.services._base import OffsetPagination, SQLSpecService, StatementFilter

if TYPE_CHECKING:
    from uuid import UUID

__all__ = ["UserOAuthAccountService"]


class UserOAuthAccountService(SQLSpecService):
    """Handles database operations for user OAuth external authorization."""

    async def create(self, data: s.OauthAccount) -> s.OauthAccount:
        """Create a new OAuth account."""
        return await self.driver.select_one(
            sql.insert("oauth_account")
            .values(**schema_dump(data, exclude_unset=True))
            .returning(
                "id",
                "oauth_name",
                "access_token",
                "account_id",
                "account_email",
                "expires_at",
                "refresh_token",
                "user_id",
                "created_at",
                "updated_at",
            ),
            schema_type=s.OauthAccount,
        )

    async def update(self, account_id: UUID, data: dict[str, Any]) -> s.OauthAccount:
        """Update an existing OAuth account."""
        return await self.driver.select_one(
            sql.update("oauth_account")
            .set(**data)
            .where_eq("id", account_id)
            .returning(
                "id",
                "oauth_name",
                "access_token",
                "account_id",
                "account_email",
                "expires_at",
                "refresh_token",
                "user_id",
                "created_at",
                "updated_at",
            ),
            schema_type=s.OauthAccount,
        )

    async def delete(self, account_id: UUID) -> s.OauthAccount:
        """Delete an OAuth account."""
        return await self.driver.select_one(
            sql.delete("oauth_account")
            .where_eq("id", account_id)
            .returning(
                "id",
                "oauth_name",
                "access_token",
                "account_id",
                "account_email",
                "expires_at",
                "refresh_token",
                "user_id",
                "created_at",
                "updated_at",
            ),
            schema_type=s.OauthAccount,
        )

    async def get_one(self, account_id: UUID) -> s.OauthAccount:
        """Get a single OAuth account by ID."""
        return await self.get_or_404(
            sql.select(
                "id",
                "oauth_name",
                "access_token",
                "account_id",
                "account_email",
                "expires_at",
                "refresh_token",
                "user_id",
                "created_at",
                "updated_at",
            )
            .from_("oauth_account")
            .where_eq("id", account_id),
            schema_type=s.OauthAccount,
        )

    async def get_by_oauth_id(self, oauth_name: str, account_id: str) -> s.OauthAccount | None:
        """Get OAuth account by provider name and OAuth account ID."""
        return await self.driver.select_one_or_none(
            sql.select(
                "id",
                "oauth_name",
                "access_token",
                "account_id",
                "account_email",
                "expires_at",
                "refresh_token",
                "user_id",
                "created_at",
                "updated_at",
            )
            .from_("oauth_account")
            .where_eq("oauth_name", oauth_name)
            .where_eq("account_id", account_id),
            schema_type=s.OauthAccount,
        )

    async def get_by_user_id(self, user_id: UUID) -> list[s.OauthAccount]:
        """Get all OAuth accounts for a user."""
        return await self.driver.select(
            sql.select(
                "id",
                "oauth_name",
                "access_token",
                "account_id",
                "account_email",
                "expires_at",
                "refresh_token",
                "user_id",
                "created_at",
                "updated_at",
            )
            .from_("oauth_account")
            .where_eq("user_id", user_id),
            schema_type=s.OauthAccount,
        )

    async def get_by_email(self, email: str) -> list[s.OauthAccount]:
        """Get all OAuth accounts by email address."""
        return await self.driver.select(
            sql.select(
                "id",
                "oauth_name",
                "access_token",
                "account_id",
                "account_email",
                "expires_at",
                "refresh_token",
                "user_id",
                "created_at",
                "updated_at",
            )
            .from_("oauth_account")
            .where_eq("account_email", email),
            schema_type=s.OauthAccount,
        )

    async def list_with_count(self, *filters: StatementFilter) -> OffsetPagination[s.OauthAccount]:
        """List OAuth accounts with pagination."""
        return await self.paginate(
            sql.select(
                "id",
                "oauth_name",
                "access_token",
                "account_id",
                "account_email",
                "expires_at",
                "refresh_token",
                "user_id",
                "created_at",
                "updated_at",
            )
            .from_("oauth_account")
            .order_by(sql.column("created_at").desc()),
            *filters,
            schema_type=s.OauthAccount,
        )

    async def update_access_token(
        self,
        account_id: UUID,
        access_token: str,
        expires_at: int | None = None,
    ) -> s.OauthAccount:
        """Update the access token for an OAuth account."""
        update_data: dict[str, Any] = {"access_token": access_token}
        if expires_at is not None:
            update_data["expires_at"] = expires_at

        return await self.driver.select_one(
            sql.update("oauth_account")
            .set(**update_data)
            .where_eq("id", account_id)
            .returning(
                "id",
                "oauth_name",
                "access_token",
                "account_id",
                "account_email",
                "expires_at",
                "refresh_token",
                "user_id",
                "created_at",
                "updated_at",
            ),
            schema_type=s.OauthAccount,
        )

    async def update_refresh_token(self, account_id: UUID, refresh_token: str) -> s.OauthAccount:
        """Update the refresh token for an OAuth account."""
        return await self.driver.select_one(
            sql.update("oauth_account")
            .set(refresh_token=refresh_token)
            .where_eq("id", account_id)
            .returning(
                "id",
                "oauth_name",
                "access_token",
                "account_id",
                "account_email",
                "expires_at",
                "refresh_token",
                "user_id",
                "created_at",
                "updated_at",
            ),
            schema_type=s.OauthAccount,
        )

    async def delete_by_user_and_provider(self, user_id: UUID, oauth_name: str) -> None:
        """Delete OAuth account by user ID and provider name."""
        await self.driver.execute(
            sql.delete("oauth_account").where_eq("user_id", user_id).where_eq("oauth_name", oauth_name),
        )

    async def create_or_update_oauth_account(
        self,
        user_id: UUID,
        provider_name: str,
        account_id: str,
        account_email: str,
        access_token: str,
        refresh_token: str | None = None,
        expires_at: int | None = None,
    ) -> s.OauthAccount:
        """Create or update an OAuth account for a user using upsert.

        Args:
            user_id: ID of the user
            provider_name: Name of OAuth provider (e.g., 'google', 'github')
            account_id: OAuth account ID from provider
            account_email: Email from OAuth provider
            access_token: OAuth access token
            refresh_token: OAuth refresh token (optional)
            expires_at: Token expiration timestamp (optional)

        Returns:
            Created or updated OAuth account
        """
        # Use upsert query for atomic create or update
        result = await self.driver.select_one(
            db_manager.get_sql("upsert-user-oauth-account"),
            user_id=user_id,
            provider=provider_name,
            oauth_account_id=account_id,
            oauth_account_email=account_email,
            access_token=access_token,
            refresh_token=refresh_token,
            expires_at=expires_at,
        )

        return s.OauthAccount(
            id=result["id"],
            user_id=result["user_id"],
            oauth_name=result["provider"],
            account_id=result["oauth_account_id"],
            account_email=result["oauth_account_email"],
            created_at=result["created_at"],
            updated_at=result["updated_at"],
            access_token=access_token,
            refresh_token=refresh_token,
            expires_at=expires_at,
        )

    async def find_user_by_oauth_account(self, provider_name: str, account_id: str) -> s.User | None:
        """Find a user by their OAuth account credentials.

        Args:
            provider_name: Name of OAuth provider
            account_id: OAuth account ID from provider

        Returns:
            User object if found, None otherwise
        """
        return await self.driver.select_one_or_none(
            sql.select(
                "u.id",
                "u.email",
                "u.name",
                "u.is_superuser",
                "u.is_active",
                "u.is_verified",
                "u.password_hash",
                "u.avatar_url",
                "u.created_at",
                "u.updated_at",
                "u.last_login",
            )
            .from_("oauth_account oa")
            .join("user_account u", "oa.user_id = u.id")
            .where_eq("oa.oauth_name", provider_name)
            .where_eq("oa.account_id", account_id),
            schema_type=s.User,
        )

    async def link_oauth_account(
        self,
        user_id: UUID,
        provider_name: str,
        account_id: str,
        account_email: str,
        access_token: str,
        refresh_token: str | None = None,
        expires_at: int | None = None,
    ) -> s.OauthAccount:
        """Link an OAuth account to an existing user.

        Args:
            user_id: ID of the user to link to
            provider_name: Name of OAuth provider
            account_id: OAuth account ID from provider
            account_email: Email from OAuth provider
            access_token: OAuth access token
            refresh_token: OAuth refresh token (optional)
            expires_at: Token expiration timestamp (optional)

        Returns:
            Created OAuth account

        Raises:
            ValueError: If OAuth account is already linked to another user
        """
        # Check if this OAuth account is already linked to another user
        existing_user = await self.find_user_by_oauth_account(provider_name, account_id)
        if existing_user and existing_user.id != user_id:
            msg = "OAuth account is already linked to another user"
            raise ValueError(msg)

        return await self.create_or_update_oauth_account(
            user_id,
            provider_name,
            account_id,
            account_email,
            access_token,
            refresh_token,
            expires_at,
        )

    async def unlink_oauth_account(self, user_id: UUID, provider_name: str) -> None:
        """Unlink an OAuth account from a user.

        Args:
            user_id: ID of the user
            provider_name: Name of OAuth provider
        """
        await self.delete_by_user_and_provider(user_id, provider_name)

    async def get_user_oauth_accounts(self, user_id: UUID) -> list[s.OauthAccount]:
        """Get all OAuth accounts for a user (alias for get_by_user_id)."""
        return await self.get_by_user_id(user_id)

    async def update_tokens(
        self,
        account_id: UUID,
        access_token: str,
        refresh_token: str | None = None,
        expires_at: int | None = None,
    ) -> s.OauthAccount:
        """Update OAuth tokens for an account.

        Args:
            account_id: ID of the OAuth account
            access_token: New access token
            refresh_token: New refresh token (optional)
            expires_at: New expiration timestamp (optional)

        Returns:
            Updated OAuth account
        """
        update_data: dict[str, Any] = {"access_token": access_token}
        if refresh_token is not None:
            update_data["refresh_token"] = refresh_token
        if expires_at is not None:
            update_data["expires_at"] = expires_at

        return await self.update(account_id, update_data)

    async def is_oauth_account_linked(self, provider_name: str, account_id: str) -> bool:
        """Check if an OAuth account is already linked to any user.

        Args:
            provider_name: Name of OAuth provider
            account_id: OAuth account ID from provider

        Returns:
            True if account is linked, False otherwise
        """
        return await self.exists(
            sql.select("1")
            .from_("oauth_account")
            .where_eq("oauth_name", provider_name)
            .where_eq("account_id", account_id),
        )

    async def get_oauth_statistics(self) -> dict:
        """Get OAuth account statistics."""
        return await self.driver.select_one(
            sql.select(
                "COUNT(*) as total_accounts",
                "COUNT(DISTINCT oauth_name) as unique_providers",
                "COUNT(DISTINCT user_id) as users_with_oauth",
            ).from_("oauth_account"),
        )
