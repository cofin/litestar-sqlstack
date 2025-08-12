from __future__ import annotations

from typing import TYPE_CHECKING, Any

from sqlspec import sql
from sqlspec.utils.type_guards import schema_dump

from sqlstack import schemas as s
from sqlstack.services._base import OffsetPagination, SQLSpecService, StatementFilter

if TYPE_CHECKING:
    from uuid import UUID

__all__ = ["TeamFileService"]


class TeamFileService(SQLSpecService):
    """Handles database operations for team file management."""

    async def create(self, data: s.TeamFile) -> s.TeamFile:
        """Create a new team file record."""
        return await self.driver.select_one(
            sql.insert("team_file")
            .values(**schema_dump(data, exclude_unset=True))
            .returning("id", "team_id", "name", "url", "created_at", "updated_at"),
            schema_type=s.TeamFile,
        )

    async def update(self, file_id: UUID, data: dict[str, Any]) -> s.TeamFile:
        """Update an existing team file record."""
        return await self.driver.select_one(
            sql.update("team_file")
            .set(**data, updated_at=sql.raw("NOW()"))
            .where_eq("id", file_id)
            .returning("id", "team_id", "name", "url", "created_at", "updated_at"),
            schema_type=s.TeamFile,
        )

    async def delete(self, file_id: UUID) -> s.TeamFile:
        """Delete a team file record."""
        return await self.driver.select_one(
            sql.delete("team_file")
            .where_eq("id", file_id)
            .returning("id", "team_id", "name", "url", "created_at", "updated_at"),
            schema_type=s.TeamFile,
        )

    async def get_one(self, file_id: UUID) -> s.TeamFile:
        """Get a single team file by ID."""
        return await self.get_or_404(
            sql.select("id", "team_id", "name", "url", "created_at", "updated_at")
            .from_("team_file")
            .where_eq("id", file_id),
            schema_type=s.TeamFile,
        )

    async def get_by_team_id(self, team_id: UUID) -> list[s.TeamFile]:
        """Get all files for a specific team."""
        return await self.driver.select(
            sql.select("id", "team_id", "name", "url", "created_at", "updated_at")
            .from_("team_file")
            .where_eq("team_id", team_id)
            .order_by(sql.column("created_at").desc()),
            schema_type=s.TeamFile,
        )

    async def get_by_name(self, team_id: UUID, name: str) -> s.TeamFile | None:
        """Get a team file by team ID and name."""
        return await self.driver.select_one_or_none(
            sql.select("id", "team_id", "name", "url", "created_at", "updated_at")
            .from_("team_file")
            .where_eq("team_id", team_id)
            .where_eq("name", name),
            schema_type=s.TeamFile,
        )

    async def list_with_count(self, *filters: StatementFilter) -> OffsetPagination[s.TeamFile]:
        """List team files with pagination."""
        return await self.paginate(
            sql.select("id", "team_id", "name", "url", "created_at", "updated_at")
            .from_("team_file")
            .order_by(sql.column("created_at").desc()),
            *filters,
            schema_type=s.TeamFile,
        )

    async def search_by_name(self, team_id: UUID, search_term: str, limit: int = 50) -> list[s.TeamFile]:
        """Search files by name within a team."""
        return await self.driver.select(
            sql.select("id", "team_id", "name", "url", "created_at", "updated_at")
            .from_("team_file")
            .where_eq("team_id", team_id)
            .where_ilike("name", f"%{search_term}%")
            .order_by("name")
            .limit(limit),
            schema_type=s.TeamFile,
        )

    async def get_files_by_type(self, team_id: UUID, file_extension: str) -> list[s.TeamFile]:
        """Get files by file extension/type within a team."""
        return await self.driver.select(
            sql.select("id", "team_id", "name", "url", "created_at", "updated_at")
            .from_("team_file")
            .where_eq("team_id", team_id)
            .where_ilike("name", f"%.{file_extension}")
            .order_by("name"),
            schema_type=s.TeamFile,
        )

    async def get_team_storage_stats(self, team_id: UUID) -> dict[str, Any]:
        """Get storage statistics for a team."""
        return await self.driver.select_one(
            sql.select(
                "COUNT(*) as file_count",
                "COALESCE(SUM(CAST(SUBSTRING(url FROM 'size=([0-9]+)') AS INTEGER)), 0) as total_size",
            )
            .from_("team_file")
            .where_eq("team_id", team_id),
        )

    async def get_recent_files(self, team_id: UUID, days: int = 7, limit: int = 20) -> list[s.TeamFile]:
        """Get recently uploaded files for a team."""
        return await self.driver.select(
            sql.select("id", "team_id", "name", "url", "created_at", "updated_at")
            .from_("team_file")
            .where_eq("team_id", team_id)
            .where_gte("created_at", sql.raw(f"NOW() - INTERVAL '{days} days'"))
            .order_by(sql.column("created_at").desc())
            .limit(limit),
            schema_type=s.TeamFile,
        )

    async def bulk_delete_by_team(self, team_id: UUID) -> None:
        """Delete all files for a team (used when deleting a team)."""
        await self.driver.execute(sql.delete("team_file").where_eq("team_id", team_id))

    async def update_file_url(self, file_id: UUID, new_url: str) -> s.TeamFile:
        """Update the URL for a team file (e.g., after moving storage location)."""
        return await self.driver.select_one(
            sql.update("team_file")
            .set(url=new_url, updated_at=sql.raw("NOW()"))
            .where_eq("id", file_id)
            .returning("id", "team_id", "name", "url", "created_at", "updated_at"),
            schema_type=s.TeamFile,
        )

    async def exists_by_name(self, team_id: UUID, name: str) -> bool:
        """Check if a file with the given name exists in the team."""
        return await self.exists(sql.select("1").from_("team_file").where_eq("team_id", team_id).where_eq("name", name))
