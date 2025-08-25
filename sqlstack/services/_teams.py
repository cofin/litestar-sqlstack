from __future__ import annotations

from uuid import UUID, uuid4

from sqlspec import sql
from sqlspec.utils.text import slugify
from sqlspec.utils.type_guards import schema_dump

from sqlstack import schemas as s
from sqlstack.config import db_manager
from sqlstack.services._base import LimitOffsetFilter, OffsetPagination, SQLSpecService, StatementFilter

# Constants that were in lib.constants
SUPERUSER_ACCESS_ROLE = "Superuser"


class TeamService(SQLSpecService):
    """Handles database operations for teams using SQLSpec's sql builder API."""

    async def create(self, data: s.TeamCreate) -> s.Team:
        """Create a new team with owner and tags."""
        team_data = schema_dump(data, exclude_unset=True)
        team_id = team_data.get("id", uuid4())
        team_data["id"] = team_id
        if "slug" not in team_data or not team_data["slug"]:
            team_data["slug"] = await self.get_available_slug(team_data.get("name", ""))
        owner_id = team_data.pop("owner_id", None)
        tags = team_data.pop("tags", [])
        await self.driver.select_one(
            db_manager.get_sql("create-team"),
            team_data,
            schema_type=s.Team,
        )
        if owner_id:
            await self.driver.execute(db_manager.get_sql("add-team-owner"), team_id=team_id, user_id=owner_id)
        await self._update_team_tags(team_id, tags)
        return await self._get_team_with_relationships(team_id)

    async def update(self, team_id: UUID, data: s.TeamUpdate) -> s.Team:
        """Update an existing team."""
        team_data = schema_dump(data, exclude_unset=True)
        if "name" in team_data and "slug" not in team_data:
            team_data["slug"] = await self.get_available_slug(team_data["name"])
        tags = team_data.pop("tags", None)
        team_data["team_id"] = team_id
        await self.driver.select_one(
            db_manager.get_sql("update-team"),
            team_data,
            schema_type=s.Team,
        )
        if tags is not None:
            await self._update_team_tags(team_id, tags)
        return await self._get_team_with_relationships(team_id)

    async def delete(self, team_id: UUID) -> s.Team:
        """Delete a team and all related data."""
        team = await self._get_team_with_relationships(team_id)
        await self.driver.execute(db_manager.get_sql("delete-team"), team_id=team_id)
        return team

    async def get_one(self, team_id: UUID) -> s.Team:
        """Get a single team by ID with all relationships."""
        return await self._get_team_with_relationships(team_id)

    async def get_by_slug(self, slug: str) -> s.Team | None:
        """Get a team by slug."""
        if row := (await self.driver.select_one_or_none(db_manager.get_sql("get-team-id-by-slug"), slug=slug)):
            return await self._get_team_with_relationships(row["id"])
        return None

    async def list_with_count(self, *filters: StatementFilter, user: s.User | None = None) -> OffsetPagination[s.Team]:
        """List teams with pagination and filtering."""
        if user and not self.can_view_all(user):
            stmt = db_manager.get_sql("list-teams-for-user")
            params = {"user_id": user.id}
        else:
            stmt = db_manager.get_sql("list-all-teams")
            params = {}

        data, total = await self.driver.select_with_total(stmt, params, *filters)
        limit_offset = self.driver.find_filter(LimitOffsetFilter, filters)
        teams = [await self._get_team_with_relationships(row["id"]) for row in data]
        return OffsetPagination(
            items=teams,
            limit=limit_offset.limit if limit_offset else len(teams),
            offset=limit_offset.offset if limit_offset else 0,
            total=total,
        )

    async def add_member(self, team_id: UUID, user_id: UUID, role: str = "MEMBER") -> s.TeamMember:
        """Add a user to a team."""
        return await self.driver.select_one(
            db_manager.get_sql("add-team-member"),
            team_id=team_id,
            user_id=user_id,
            role=role,
            schema_type=s.TeamMember,
        )

    async def remove_member(self, team_id: UUID, user_id: UUID) -> None:
        """Remove a user from a team."""
        await self.driver.execute(db_manager.get_sql("remove-team-member"), team_id=team_id, user_id=user_id)

    async def get_user_teams(self, user_id: UUID) -> list[s.Team]:
        """Get all teams for a user."""
        team_rows = await self.driver.select(
            db_manager.get_sql("get-teams-for-user"),
            user_id=user_id,
        )
        return [await self._get_team_with_relationships(row["id"]) for row in team_rows]

    async def search_teams(self, query: str, limit: int = 10) -> list[s.Team]:
        """Search teams by name or description."""
        team_rows = await self.driver.select(
            db_manager.get_sql("search-teams"),
            query=query,
            limit=limit,
        )
        return [await self._get_team_with_relationships(row["id"]) for row in team_rows]

    @staticmethod
    def can_view_all(user: s.User) -> bool:
        """Check if user can view all teams."""
        return any(role.role_slug == "superuser" for role in user.roles)

    async def get_available_slug(self, name: str) -> str:
        """Generate a unique slug for the given name."""
        base_slug = slugify(name)
        slug = base_slug
        counter = 1
        while await self._slug_exists(slug):
            slug = f"{base_slug}-{counter}"
            counter += 1
        return slug

    async def _slug_exists(self, slug: str) -> bool:
        """Check if a slug already exists."""
        return await self.exists(sql.select("id").from_("team").where_eq("slug", slug))

    async def _update_team_tags(self, team_id: UUID, tag_names: list[str]) -> None:
        """Update tags for a team."""
        await self.driver.execute(db_manager.get_sql("clear-team-tags"), team_id=team_id)
        for tag_name in tag_names:
            tag_row = await self.driver.select_one_or_none(
                db_manager.get_sql("upsert-tag"),
                name=tag_name,
                slug=slugify(tag_name),
            )
            if not tag_row:
                tag_row = await self.driver.select_one(db_manager.get_sql("get-tag-id-by-name"), name=tag_name)
            await self.driver.execute(db_manager.get_sql("add-team-tag"), team_id=team_id, tag_id=tag_row["id"])

    async def _get_team_with_relationships(self, team_id: UUID) -> s.Team:
        """Get a team with all its relationships loaded."""
        return await self.get_or_404(
            db_manager.get_sql("get-team-with-relationships"),
            team_id=team_id,
            schema_type=s.Team,
            error_message=f"Team {team_id} not found",
        )
