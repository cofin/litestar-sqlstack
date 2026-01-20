from datetime import datetime
from uuid import UUID

import msgspec

from sqlstack.lib.schema import CamelizedBaseStruct
from sqlstack.utils.types import Slug

__all__ = ("Role", "RoleCreate", "RoleUpdate", "UserRole", "UserRoleAdd", "UserRoleCreate", "UserRoleRevoke")


class Role(CamelizedBaseStruct):
    """Holds role details for a user.

    This is nested in the User Model for 'roles'
    """

    id: UUID
    slug: str
    name: str
    description: str | None
    created_at: datetime
    updated_at: datetime


class RoleCreate(CamelizedBaseStruct):
    name: str
    description: str | None = None


class RoleUpdate(CamelizedBaseStruct, omit_defaults=True):
    name: str | msgspec.UnsetType | None = msgspec.UNSET
    description: str | msgspec.UnsetType | None = msgspec.UNSET


class UserRole(CamelizedBaseStruct):
    """Holds role details for a user.

    This is nested in the User Model for 'roles'
    """

    role_id: UUID
    role_slug: Slug
    role_name: str
    assigned_at: datetime


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
