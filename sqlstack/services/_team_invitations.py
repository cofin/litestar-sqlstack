from __future__ import annotations

from typing import TYPE_CHECKING, Any

from sqlspec import StatementConfig, sql
from sqlspec.utils.type_guards import schema_dump

from sqlstack import schemas as s
from sqlstack.services._base import SQLSpecService, StatementFilter

if TYPE_CHECKING:
    from datetime import datetime
    from uuid import UUID

    from sqlstack.services import OffsetPagination

__all__ = ["TeamInvitationService"]


class TeamInvitationService(SQLSpecService):
    """Handles database operations for team invitations."""

    async def create(self, data: s.TeamInvitationCreate, team_id: UUID) -> s.TeamInvitation:
        """Create a new team invitation."""
        invitation_data = schema_dump(data, exclude_unset=True)
        invitation_data["team_id"] = team_id

        return await self.driver.select_one(
            sql.insert("team_invitation")
            .values(**invitation_data)
            .returning(
                "id",
                "team_id",
                "email",
                "role",
                "created_at",
                "updated_at",
                "accepted_at",
                "accepted_by",
                "expires_at",
            ),
            schema_type=s.TeamInvitation,
        )

    async def update(self, invitation_id: UUID, data: dict[str, Any]) -> s.TeamInvitation:
        """Update an existing team invitation."""
        return await self.driver.select_one(
            sql.update("team_invitation")
            .set(**data, updated_at=sql.raw("NOW()"))
            .where_eq("id", invitation_id)
            .returning(
                "id",
                "team_id",
                "email",
                "role",
                "created_at",
                "updated_at",
                "accepted_at",
                "accepted_by",
                "expires_at",
            ),
            schema_type=s.TeamInvitation,
        )

    async def delete(self, invitation_id: UUID) -> s.TeamInvitation:
        """Delete a team invitation."""
        return await self.driver.select_one(
            sql.delete("team_invitation")
            .where_eq("id", invitation_id)
            .returning(
                "id",
                "team_id",
                "email",
                "role",
                "created_at",
                "updated_at",
                "accepted_at",
                "accepted_by",
                "expires_at",
            ),
            schema_type=s.TeamInvitation,
        )

    async def get_one(self, invitation_id: UUID) -> s.TeamInvitation:
        """Get a single team invitation by ID."""
        return await self.get_or_404(
            sql.select(
                "id",
                "team_id",
                "email",
                "role",
                "created_at",
                "updated_at",
                "accepted_at",
                "accepted_by",
                "expires_at",
            )
            .from_("team_invitation")
            .where_eq("id", invitation_id),
            schema_type=s.TeamInvitation,
        )

    async def get_by_team_id(self, team_id: UUID) -> list[s.TeamInvitation]:
        """Get all invitations for a specific team."""
        return await self.driver.select(
            sql.select(
                "id",
                "team_id",
                "email",
                "role",
                "created_at",
                "updated_at",
                "accepted_at",
                "accepted_by",
                "expires_at",
            )
            .from_("team_invitation")
            .where_eq("team_id", team_id)
            .order_by(sql.column("created_at").desc()),
            schema_type=s.TeamInvitation,
        )

    async def get_by_email(self, email: str) -> list[s.TeamInvitation]:
        """Get all invitations for a specific email address."""
        return await self.driver.select(
            sql.select(
                "id",
                "team_id",
                "email",
                "role",
                "created_at",
                "updated_at",
                "accepted_at",
                "accepted_by",
                "expires_at",
            )
            .from_("team_invitation")
            .where_eq("email", email)
            .order_by(sql.column("created_at").desc()),
            schema_type=s.TeamInvitation,
        )

    async def get_by_email_and_team(self, email: str, team_id: UUID) -> s.TeamInvitation | None:
        """Get invitation by email and team (to check for duplicates)."""
        return await self.driver.select_one_or_none(
            sql.select(
                "id",
                "team_id",
                "email",
                "role",
                "created_at",
                "updated_at",
                "accepted_at",
                "accepted_by",
                "expires_at",
            )
            .from_("team_invitation")
            .where_eq("email", email)
            .where_eq("team_id", team_id),
            schema_type=s.TeamInvitation,
        )

    async def list_with_count(
        self, *filters: StatementFilter, statement_config: StatementConfig | None = None, **kwargs: dict[str, Any]
    ) -> OffsetPagination[s.TeamInvitation]:
        """List team invitations with pagination."""
        return await self.paginate(
            sql.select(
                "id",
                "team_id",
                "email",
                "role",
                "created_at",
                "updated_at",
                "accepted_at",
                "accepted_by",
                "expires_at",
            )
            .from_("team_invitation")
            .order_by(sql.column("created_at").desc()),
            *filters,
            statement_config=statement_config,
            **kwargs,
            schema_type=s.TeamInvitation,
        )

    async def get_pending_invitations(self, team_id: UUID) -> list[s.TeamInvitation]:
        """Get all pending (not accepted/expired) invitations for a team."""
        return await self.driver.select(
            sql.select(
                "id",
                "team_id",
                "email",
                "role",
                "created_at",
                "updated_at",
                "accepted_at",
                "accepted_by",
                "expires_at",
            )
            .from_("team_invitation")
            .where_eq("team_id", team_id)
            .where_is_null("accepted_at")
            .where_gte("expires_at", sql.raw("NOW()"))
            .order_by(sql.column("created_at").desc()),
            schema_type=s.TeamInvitation,
        )

    async def get_expired_invitations(self) -> list[s.TeamInvitation]:
        """Get all expired invitations."""
        return await self.driver.select(
            sql.select(
                "id",
                "team_id",
                "email",
                "role",
                "created_at",
                "updated_at",
                "accepted_at",
                "accepted_by",
                "expires_at",
            )
            .from_("team_invitation")
            .where_is_null("accepted_at")
            .where_lt("expires_at", sql.raw("NOW()"))
            .order_by(sql.column("expires_at").desc()),
            schema_type=s.TeamInvitation,
        )

    async def accept_invitation(self, invitation_id: UUID, user_id: UUID) -> s.TeamInvitation:
        """Mark an invitation as accepted."""
        return await self.driver.select_one(
            sql.update("team_invitation")
            .set(accepted_at=sql.raw("NOW()"), accepted_by=user_id)
            .where_eq("id", invitation_id)
            .returning(
                "id",
                "team_id",
                "email",
                "role",
                "created_at",
                "updated_at",
                "accepted_at",
                "accepted_by",
                "expires_at",
            ),
            schema_type=s.TeamInvitation,
        )

    async def is_invitation_valid(self, invitation_id: UUID) -> bool:
        """Check if an invitation is still valid (not expired and not accepted)."""
        return await self.exists(
            sql.select("1")
            .from_("team_invitation")
            .where_eq("id", invitation_id)
            .where_is_null("accepted_at")
            .where_gte("expires_at", sql.raw("NOW()")),
        )

    async def bulk_delete_expired(self) -> int:
        """Delete all expired invitations and return count of deleted records."""
        result = await self.driver.execute(
            sql.delete("team_invitation").where_is_null("accepted_at").where_lt("expires_at", sql.raw("NOW()")),
        )
        return result.total_count or 0

    async def extend_invitation(self, invitation_id: UUID, new_expiry: datetime) -> s.TeamInvitation:
        """Extend the expiration date of an invitation."""
        return await self.driver.select_one(
            sql.update("team_invitation")
            .set(expires_at=new_expiry, updated_at=sql.raw("NOW()"))
            .where_eq("id", invitation_id)
            .returning(
                "id",
                "team_id",
                "email",
                "role",
                "created_at",
                "updated_at",
                "accepted_at",
                "accepted_by",
                "expires_at",
            ),
            schema_type=s.TeamInvitation,
        )

    async def get_invitation_stats(self, team_id: UUID) -> dict[str, Any]:
        """Get invitation statistics for a team."""
        return await self.driver.select_one(
            sql.select(
                "COUNT(*) as total_invitations",
                "COUNT(CASE WHEN accepted_at IS NOT NULL THEN 1 END) as accepted_count",
                "COUNT(CASE WHEN accepted_at IS NULL AND expires_at > NOW() THEN 1 END) as pending_count",
                "COUNT(CASE WHEN accepted_at IS NULL AND expires_at <= NOW() THEN 1 END) as expired_count",
            )
            .from_("team_invitation")
            .where_eq("team_id", team_id),
        )

    async def revoke_invitation(self, invitation_id: UUID) -> None:
        """Revoke an invitation by deleting it."""
        await self.driver.execute(sql.delete("team_invitation").where_eq("id", invitation_id))

    async def bulk_invite(self, team_id: UUID, invitations: list[s.TeamInvitationCreate]) -> list[s.TeamInvitation]:
        """Create multiple invitations at once."""
        created_invitations: list[s.TeamInvitation] = []
        for invitation_data in invitations:
            invitation = await self.create(invitation_data, team_id)
            created_invitations.append(invitation)
        return created_invitations
