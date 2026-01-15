from datetime import date

import msgspec

from sqlstack.domain.accounts.schemas._roles import UserRole
from sqlstack.lib.schema import CamelizedBaseStruct
from sqlstack.utils.types import Email, Name, Password

__all__ = (
    "ProfileUpdate",
    "User",
    "UserCreate",
    "UserUpdate",
)


class User(CamelizedBaseStruct):
    """User properties to use for a response."""

    id: msgspec.field(name="id")  # type: ignore
    email: str
    joined_at: date | None = None
    name: str | None = None
    avatar_url: str | None = None
    is_active: bool = False
    is_verified: bool = False
    is_superuser: bool = False
    verified_at: date | None = None
    has_password: bool = False
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


class ProfileUpdate(CamelizedBaseStruct, omit_defaults=True):
    name: Name | msgspec.UnsetType | None = msgspec.UNSET
