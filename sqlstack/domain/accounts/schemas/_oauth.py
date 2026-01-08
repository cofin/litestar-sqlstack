from datetime import datetime
from typing import Any
from uuid import UUID

from sqlstack.lib.schema import CamelizedBaseStruct
from sqlstack.lib.types import Email

__all__ = (
    "OAuthAccountInfo",
    "OAuthAuthorization",
    "OauthAccount",
    "UserOAuthAccount",
    "UserOAuthAccountCreate",
    "UserOAuthAccountUpdate",
)


class OAuthAuthorization(CamelizedBaseStruct):
    """OAuth authorization URL and state."""

    authorization_url: str
    state: str | None = None


class OAuthAccountInfo(CamelizedBaseStruct):
    """OAuth account information."""

    provider: str
    oauth_id: str
    email: str
    linked_at: datetime
    name: str | None = None
    avatar_url: str | None = None
    last_login_at: datetime | None = None


class OauthAccount(CamelizedBaseStruct):
    """Holds linked Oauth details for a user."""

    id: UUID
    user_id: UUID
    oauth_name: str
    account_id: str
    account_email: Email
    created_at: datetime
    updated_at: datetime
    access_token: str | None = None
    expires_at: int | None = None
    refresh_token: str | None = None
    token_expires_at: datetime | None = None
    scope: str | None = None
    provider_user_data: dict[str, Any] | None = None
    last_login_at: datetime | None = None


class UserOAuthAccount(CamelizedBaseStruct):
    """User OAuth account details."""

    id: UUID
    user_id: UUID
    provider: str
    oauth_account_id: str
    created_at: datetime
    updated_at: datetime
    oauth_account_email: str | None = None


class UserOAuthAccountCreate(CamelizedBaseStruct):
    """Schema for creating a user OAuth account."""

    user_id: UUID
    provider: str
    oauth_account_id: str
    oauth_account_email: Email | None = None


class UserOAuthAccountUpdate(CamelizedBaseStruct):
    """Schema for updating a user OAuth account."""

    oauth_account_email: Email | None = None
