from datetime import date, datetime
from uuid import UUID

import msgspec

from sqlstack.lib.types import Email, Name, Password, Slug
from sqlstack.schemas._enums import TeamRoles
from sqlstack.schemas.base import CamelizedBaseStruct

__all__ = (
    "AccountLogin",
    "AccountRegister",
    "OauthAccount",
    "PasswordUpdate",
    "PasswordVerify",
    "ProfileUpdate",
    "User",
    "UserCreate",
    "UserOAuthAccount",
    "UserOAuthAccountCreate",
    "UserOAuthAccountUpdate",
    "UserRole",
    "UserRoleAdd",
    "UserRoleCreate",
    "UserRoleRevoke",
    "UserTeam",
    "UserUpdate",
)


class UserTeam(CamelizedBaseStruct):
    """Holds team details for a user.

    This is nested in the User Model for 'team'
    """

    team_id: UUID
    team_name: str
    is_owner: bool = False
    role: TeamRoles = TeamRoles.MEMBER


class UserRole(CamelizedBaseStruct):
    """Holds role details for a user.

    This is nested in the User Model for 'roles'
    """

    role_id: UUID
    role_slug: Slug
    role_name: str
    assigned_at: datetime


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


class User(CamelizedBaseStruct):
    """User properties to use for a response."""

    id: UUID
    email: str
    joined_at: date | None = None
    name: str | None = None
    avatar_url: str | None = None
    is_active: bool = False
    is_verified: bool = False
    is_superuser: bool = False
    verified_at: date | None = None
    has_password: bool = False
    teams: list[UserTeam] = msgspec.field(default_factory=lambda: list[UserTeam]())
    roles: list[UserRole] = msgspec.field(default_factory=lambda: list[UserRole]())


class UserCreate(CamelizedBaseStruct):
    email: str
    password: str
    name: str | None = None
    is_active: bool = True
    is_verified: bool = False
    verified_at: date | None = None
    joined_at: date | None = None
    is_superuser: bool = False


class UserUpdate(CamelizedBaseStruct, omit_defaults=True):
    email: Email | msgspec.UnsetType | None = msgspec.UNSET
    password: Password | msgspec.UnsetType | None = msgspec.UNSET
    name: Name | msgspec.UnsetType | None = msgspec.UNSET
    is_active: bool | msgspec.UnsetType | None = msgspec.UNSET
    is_verified: bool | msgspec.UnsetType | None = msgspec.UNSET
    verified_at: date | msgspec.UnsetType | None = msgspec.UNSET
    joined_at: date | msgspec.UnsetType | None = msgspec.UNSET
    is_superuser: bool | msgspec.UnsetType | None = msgspec.UNSET


class AccountLogin(CamelizedBaseStruct):
    username: str
    password: Password


class PasswordUpdate(CamelizedBaseStruct):
    current_password: Password
    new_password: Password


class PasswordVerify(CamelizedBaseStruct):
    current_password: Password


class ProfileUpdate(CamelizedBaseStruct, omit_defaults=True):
    name: Name | msgspec.UnsetType | None = msgspec.UNSET


class AccountRegister(CamelizedBaseStruct):
    email: Email
    password: Password
    name: Name | None = None
    initial_team_name: str | msgspec.UnsetType | None = msgspec.UNSET


class UserRoleAdd(CamelizedBaseStruct):
    """User role add ."""

    user_name: str


class UserRoleRevoke(CamelizedBaseStruct):
    """User role revoke ."""

    user_name: str


class UserRoleCreate(CamelizedBaseStruct):
    """Schema for creating a user role assignment."""

    user_id: UUID
    role_id: UUID


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
