from datetime import datetime
from uuid import UUID

import msgspec

from sqlstack.lib.schema import CamelizedBaseStruct

__all__ = ("Role", "RoleCreate", "RoleUpdate")


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
