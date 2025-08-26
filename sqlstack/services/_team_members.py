from __future__ import annotations

from typing import TYPE_CHECKING

from sqlspec import sql

from sqlstack import schemas as s
from sqlstack.schemas._enums import TeamRoles
from sqlstack.services._base import OffsetPagination, SQLSpecService, StatementFilter

if TYPE_CHECKING:
    from uuid import UUID

__all__ = ["TeamMemberService"]


class TeamMemberService(SQLSpecService):
    """Handles database operations for team members."""

    async def add_member_to_team(
        self,
        team_id: UUID,
        user_id: UUID,
        role: TeamRoles = TeamRoles.MEMBER,
    ) -> s.TeamMember:
        """Add a user as a member to a team."""
        # First insert the team member
        member = await self.driver.select_one(
            sql.insert("team_member")
            .columns("team_id", "user_id", "role", "is_owner", "joined_at")
            .values(team_id, user_id, role, False, sql.raw("NOW()"))
            .returning("id", "user_id", "role", "is_owner", "joined_at"),
            schema_type=s.TeamMember,
        )

        # Then fetch with user details for complete TeamMember schema
        return await self.driver.select_one(
            sql.select(
                "tm.id",
                "tm.team_id",
                "tm.user_id",
                "u.email",
                "u.name",
                "tm.role",
                "tm.is_owner",
                "tm.joined_at",
            )
            .from_("team_member tm")
            .join("user_account u", "tm.user_id = u.id")
            .where_eq("tm.id", member.id),
            schema_type=s.TeamMember,
        )

    async def remove_member_from_team(self, team_id: UUID, user_id: UUID) -> None:
        """Remove a user from a team."""
        await self.driver.execute(sql.delete("team_member").where_eq("team_id", team_id).where_eq("user_id", user_id))

    async def update_member_role(self, team_id: UUID, user_id: UUID, role: TeamRoles) -> s.TeamMember:
        """Update a team member's role."""
        # Update the member's role
        updated = await self.driver.select_one(
            sql.update("team_member")
            .set(role=role, updated_at=sql.raw("NOW()"))
            .where_eq("team_id", team_id)
            .where_eq("user_id", user_id)
            .returning("id"),
        )

        # Fetch with user details for complete TeamMember schema
        return await self.driver.select_one(
            sql.select(
                "tm.id",
                "tm.team_id",
                "tm.user_id",
                "u.email",
                "u.name",
                "tm.role",
                "tm.is_owner",
                "tm.joined_at",
            )
            .from_("team_member tm")
            .join("user_account u", "tm.user_id = u.id")
            .where_eq("tm.id", updated["id"]),
            schema_type=s.TeamMember,
        )

    async def get_team_members(self, team_id: UUID) -> list[s.TeamMember]:
        """Get all members of a specific team."""
        return await self.driver.select(
            sql.select(
                "tm.id",
                "tm.team_id",
                "tm.user_id",
                "u.email",
                "u.name",
                "tm.role",
                "tm.is_owner",
                "tm.joined_at",
            )
            .from_("team_member tm")
            .join("user_account u", "tm.user_id = u.id")
            .where_eq("tm.team_id", team_id)
            .order_by("u.name"),
            schema_type=s.TeamMember,
        )

    async def get_user_teams(self, user_id: UUID) -> list[s.TeamMember]:
        """Get all teams a user is a member of."""
        return await self.driver.select(
            sql.select(
                "tm.id",
                "tm.team_id",
                "tm.user_id",
                "u.email",
                "u.name",
                "tm.role",
                "tm.is_owner",
                "tm.joined_at",
            )
            .from_("team_member tm")
            .join("user_account u", "tm.user_id = u.id")
            .where_eq("tm.user_id", user_id)
            .order_by("tm.joined_at DESC"),
            schema_type=s.TeamMember,
        )

    async def is_member_of_team(self, team_id: UUID, user_id: UUID) -> bool:
        """Check if a user is a member of a specific team."""
        return await self.exists(
            sql.select("1").from_("team_member").where_eq("team_id", team_id).where_eq("user_id", user_id),
        )

    async def get_member_role(self, team_id: UUID, user_id: UUID) -> TeamRoles | None:
        """Get a user's role in a specific team."""
        result = await self.driver.select_one_or_none(
            sql.select("role").from_("team_member").where_eq("team_id", team_id).where_eq("user_id", user_id),
        )
        return result["role"] if result else None

    async def is_team_owner(self, team_id: UUID, user_id: UUID) -> bool:
        """Check if a user is the owner of a specific team."""
        return await self.exists(
            sql.select("1")
            .from_("team_member")
            .where_eq("team_id", team_id)
            .where_eq("user_id", user_id)
            .where_eq("is_owner", True),
        )

    async def set_team_owner(self, team_id: UUID, user_id: UUID) -> s.TeamMember:
        """Set a user as the owner of a team."""
        # First, remove owner status from all current members
        await self.driver.execute(sql.update("team_member").set(is_owner=False).where_eq("team_id", team_id))

        # Then set the new owner
        updated = await self.driver.select_one(
            sql.update("team_member")
            .set(is_owner=True, role=TeamRoles.ADMIN)
            .where_eq("team_id", team_id)
            .where_eq("user_id", user_id)
            .returning("id"),
        )

        # Fetch with user details for complete TeamMember schema
        return await self.driver.select_one(
            sql.select(
                "tm.id",
                "tm.team_id",
                "tm.user_id",
                "u.email",
                "u.name",
                "tm.role",
                "tm.is_owner",
                "tm.joined_at",
            )
            .from_("team_member tm")
            .join("user_account u", "tm.user_id = u.id")
            .where_eq("tm.id", updated["id"]),
            schema_type=s.TeamMember,
        )

    async def get_team_member_count(self, team_id: UUID) -> int:
        """Get the number of members in a team."""
        result = await self.driver.select_one(
            sql.select("COUNT(*) as count").from_("team_member").where_eq("team_id", team_id),
        )
        return int(result["count"])

    async def list_all_memberships(self, *filters: StatementFilter) -> OffsetPagination[s.TeamMember]:
        """List all team memberships with pagination."""
        return await self.paginate(
            sql.select(
                "tm.id",
                "tm.team_id",
                "tm.user_id",
                "u.email",
                "u.name",
                "tm.role",
                "tm.is_owner",
                "tm.joined_at",
            )
            .from_("team_member tm")
            .join("user_account u", "tm.user_id = u.id")
            .order_by("tm.joined_at DESC"),
            *filters,
            schema_type=s.TeamMember,
        )

    async def bulk_remove_members(self, team_id: UUID, user_ids: list[UUID]) -> None:
        """Remove multiple users from a team."""
        await self.driver.execute(sql.delete("team_member").where_eq("team_id", team_id).where_in("user_id", user_ids))
