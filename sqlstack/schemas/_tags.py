# Standard Library

from datetime import datetime
from uuid import UUID

import msgspec

from sqlstack.lib.schema import CamelizedBaseStruct


# Properties to receive via API on creation
class Tag(CamelizedBaseStruct):
    """Tag Information."""

    id: UUID
    slug: str
    name: str
    description: str | None
    created_at: datetime
    updated_at: datetime


class TagCreate(CamelizedBaseStruct):
    """Tag Create Properties."""

    name: str
    description: str | None = None


class TagUpdate(CamelizedBaseStruct, omit_defaults=True):
    """Tag Update Properties."""

    name: str | msgspec.UnsetType | None = msgspec.UNSET
    description: str | msgspec.UnsetType | None = msgspec.UNSET
