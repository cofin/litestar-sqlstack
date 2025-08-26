from datetime import datetime
from uuid import UUID

import msgspec

from sqlstack.schemas._enums import TeamRoles
from sqlstack.schemas.base import CamelizedBaseStruct

__all__ = (
    "Team",
    "TeamCreate",
    "TeamInvitation",
    "TeamInvitationCreate",
    "TeamMember",
    "TeamMemberCreate",
    "TeamMemberModify",
    "TeamTag",
    "TeamUpdate",
)


class TeamTag(CamelizedBaseStruct):
    id: UUID
    slug: str
    name: str


class TeamMember(CamelizedBaseStruct):
    id: UUID
    team_id: UUID
    user_id: UUID
    email: str
    name: str | None = None
    role: TeamRoles | None = TeamRoles.MEMBER
    is_owner: bool | None = False
    joined_at: datetime | None = None


class Team(CamelizedBaseStruct, kw_only=True):
    id: UUID
    slug: str
    name: str
    created_at: datetime
    updated_at: datetime
    description: str | None = None
    is_active: bool = True
    members: list[TeamMember] = []
    tags: list[TeamTag] = []


class TeamCreate(CamelizedBaseStruct):
    name: str
    description: str | None = None
    is_active: bool = True
    tags: list[str] = []


class TeamUpdate(CamelizedBaseStruct, omit_defaults=True):
    name: str | msgspec.UnsetType | None = msgspec.UNSET
    description: str | msgspec.UnsetType | None = msgspec.UNSET
    is_active: bool | msgspec.UnsetType | None = msgspec.UNSET
    tags: list[str] | msgspec.UnsetType | None = msgspec.UNSET


class TeamMemberModify(CamelizedBaseStruct):
    """Team Member Modify."""

    user_name: str
    role: TeamRoles


class TeamInvitationCreate(CamelizedBaseStruct):
    email: str
    role: TeamRoles


class TeamInvitation(CamelizedBaseStruct, kw_only=True):
    id: UUID
    team_id: UUID
    email: str
    role: TeamRoles
    invited_by_email: str
    created_at: datetime
    updated_at: datetime
    is_accepted: bool = False
    invited_by_id: UUID | None = None


class TeamMemberCreate(CamelizedBaseStruct):
    """Schema for creating a team member."""

    user_id: UUID
    role: str | None = "MEMBER"
