from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from sqlspec import sql

from sqlstack.domain.accounts import schemas as s
from sqlstack.lib.service import SQLSpecAsyncService

if TYPE_CHECKING:
    from uuid import UUID

    from httpx_oauth.oauth2 import OAuth2Token


class UserOAuthAccountService(SQLSpecAsyncService):
    """Handles database operations for user OAuth external authorization."""

    async def can_unlink_oauth(self, user: s.User) -> tuple[bool, str]:
        """Check if user can safely unlink an OAuth provider.

        Args:
            user: The user attempting to unlink.

        Returns:
            Tuple of (can_unlink, reason_if_not).
        """
        if user.has_password:
            return True, ""

        oauth_count = await self.count(user_id=user.id)
        if oauth_count <= 1:
            return False, "Cannot unlink your only login method. Please set a password first."
        return True, ""

    async def count(self, user_id: UUID) -> int:
        return await self.driver.select_value(
            sql.select(sql.count()).from_("user_oauth_account").where_eq("user_id", user_id)
        )

    async def create_or_update_oauth_account(
        self,
        user_id: UUID,
        provider: str,
        oauth_data: dict[str, Any],
        token_data: OAuth2Token,
    ) -> s.OauthAccount:
        """Create or update OAuth account with token data."""
        account_id = oauth_data.get("id", oauth_data.get("sub", ""))
        account_email = oauth_data.get("email", "")
        return await self.link_or_update_oauth(
            user_id=user_id,
            provider=provider,
            account_id=account_id,
            account_email=account_email,
            access_token=token_data["access_token"],
            refresh_token=token_data.get("refresh_token"),
            expires_at=token_data.get("expires_at"),
            scopes=token_data.get("scope"),
            provider_user_data=oauth_data,
            last_login_at=datetime.now(UTC),
        )

    async def link_or_update_oauth(
        self,
        user_id: UUID,
        provider: str,
        account_id: str,
        account_email: str | None,
        access_token: str,
        refresh_token: str | None = None,
        expires_at: int | None = None,
        scopes: list[str] | str | None = None,
        provider_user_data: dict[str, Any] | None = None,
        last_login_at: datetime | None = None,
    ) -> s.OauthAccount:
        """Link a new OAuth account or update existing one."""
        scope_value = " ".join(scopes) if isinstance(scopes, list) else scopes
        token_expires_at = datetime.fromtimestamp(expires_at, tz=UTC) if expires_at else None
        
        account_data: dict[str, Any] = {
            "user_id": user_id,
            "oauth_name": provider,
            "account_id": account_id,
            "account_email": account_email,
            "access_token": access_token,
        }
        if refresh_token is not None:
            account_data["refresh_token"] = refresh_token
        if expires_at is not None:
            account_data["expires_at"] = expires_at
            account_data["token_expires_at"] = token_expires_at
        if scope_value is not None:
            account_data["scope"] = scope_value
        if provider_user_data is not None:
            account_data["provider_user_data"] = provider_user_data
        if last_login_at is not None:
            account_data["last_login_at"] = last_login_at

        existing = await self.get_one_or_none(user_id=user_id, oauth_name=provider)
        
        if existing:
            account_data["updated_at"] = sql.raw("NOW()")
            await self.driver.execute(
                sql.update("user_oauth_account").set(**account_data).where_eq("id", existing.id)
            )
            return await self.get_one(id=existing.id)
        
        account_data["id"] = sql.raw("gen_random_uuid()")
        account_data["created_at"] = sql.raw("NOW()")
        account_data["updated_at"] = sql.raw("NOW()")
        
        # Insert
        stmt = sql.insert("user_oauth_account").columns(*account_data.keys()).values(*account_data.values()).returning("id")
        new_id = await self.driver.select_value(stmt)
        return await self.get_one(id=new_id)

    async def unlink_oauth_account(
        self,
        user_id: UUID,
        provider: str,
    ) -> bool:
        """Unlink OAuth account from user."""
        existing = await self.get_one_or_none(user_id=user_id, oauth_name=provider)

        if existing:
            await self.driver.execute(sql.delete("user_oauth_account").where_eq("id", existing.id))
            return True

        return False

    async def get_by_provider_account_id(
        self,
        provider: str,
        account_id: str,
    ) -> s.OauthAccount | None:
        """Get an OAuth account by provider and account ID."""
        return await self.get_one_or_none(oauth_name=provider, account_id=account_id)

    async def get_one_or_none(self, **kwargs: Any) -> s.OauthAccount | None:
        stmt = sql.select("*").from_("user_oauth_account")
        for k, v in kwargs.items():
            stmt = stmt.where_eq(k, v)
        return await self.driver.select_one_or_none(stmt, schema_type=s.OauthAccount)

    async def get_one(self, **kwargs: Any) -> s.OauthAccount:
        res = await self.get_one_or_none(**kwargs)
        if not res:
            raise ValueError("OAuth Account not found")
        return res
    
    async def list_and_count(self, *filters: Any, **kwargs: Any) -> tuple[list[s.OauthAccount], int]:
        stmt = sql.select("*").from_("user_oauth_account")
        
        for k, v in kwargs.items():
             stmt = stmt.where_eq(k, v)

        total = await self.driver.select_value(sql.select(sql.count()).from_("user_oauth_account"))
        
        results = await self.driver.select(stmt, schema_type=s.OauthAccount)
        return results, total