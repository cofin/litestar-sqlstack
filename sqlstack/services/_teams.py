from __future__ import annotations

from uuid import UUID, uuid4

from sqlspec import sql
from sqlspec.utils.text import slugify
from sqlspec.utils.type_guards import schema_dump

from sqlstack import schemas as s
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
            team_data["slug"] = await self._get_available_slug(team_data.get("name", ""))
        owner_id = team_data.pop("owner_id", None)
        tags = team_data.pop("tags", [])
        await self.driver.select_one(
            sql.insert("team")
            .values(**team_data)
            .returning("id", "name", "description", "slug", "created_at", "updated_at"),
            schema_type=s.Team,
        )
        if owner_id:
            await self.driver.execute(
                sql.insert("team_member").values(team_id=team_id, user_id=owner_id, role="ADMIN", is_owner=True)
            )
        await self._update_team_tags(team_id, tags)
        return await self._get_team_with_relationships(team_id)

    async def update(self, team_id: UUID, data: s.TeamUpdate) -> s.Team:
        """Update an existing team."""
        team_data = schema_dump(data, exclude_unset=True)
        if "name" in team_data and "slug" not in team_data:
            team_data["slug"] = await self._get_available_slug(team_data["name"])
        tags = team_data.pop("tags", None)
        await self.driver.select_one(
            sql.update("team")
            .set(**team_data)
            .where_eq("id", team_id)
            .returning("id", "name", "description", "slug", "created_at", "updated_at"),
            schema_type=s.Team,
        )
        if tags is not None:
            await self._update_team_tags(team_id, tags)
        return await self._get_team_with_relationships(team_id)

    async def delete(self, team_id: UUID) -> s.Team:
        """Delete a team and all related data."""
        team = await self._get_team_with_relationships(team_id)
        await self.driver.execute(sql.delete("team").where_eq("id", team_id))
        return team

    async def get_one(self, team_id: UUID) -> s.Team:
        """Get a single team by ID with all relationships."""
        return await self._get_team_with_relationships(team_id)

    async def get_by_slug(self, slug: str) -> s.Team | None:
        """Get a team by slug."""
        if row := (await self.driver.select_one_or_none(sql.select("id").from_("team").where_eq("slug", slug))):
            return await self._get_team_with_relationships(row["id"])
        return None

    async def list_with_count(self, *filters: StatementFilter, user: s.User | None = None) -> OffsetPagination[s.Team]:
        """List teams with pagination and filtering."""
        stmt = sql.select("t.id").from_("team t")
        if user and not self.can_view_all(user):
            stmt = stmt.where_in("t.id", sql.select("team_id").from_("team_member").where_eq("user_id", user.id))
        stmt = stmt.order_by(sql.column("t.name").asc())
        total = await self.driver.select_value(stmt.with_only_select(sql.count()))
        limit_offset = next(
            (f for f in filters if isinstance(f, LimitOffsetFilter)), LimitOffsetFilter(limit=20, offset=0)
        )
        team_rows = await self.driver.select(stmt.limit(limit_offset.limit).offset(limit_offset.offset))
        teams = [await self._get_team_with_relationships(row["id"]) for row in team_rows]
        return OffsetPagination(
            items=teams,
            limit=limit_offset.limit,
            offset=limit_offset.offset,
            total=total,
        )

    async def add_member(self, team_id: UUID, user_id: UUID, role: str = "MEMBER") -> s.TeamMember:
        """Add a user to a team."""
        return await self.driver.select_one(
            sql.insert("team_member")
            .values(team_id=team_id, user_id=user_id, role=role, is_owner=False)
            .on_conflict(["team_id", "user_id"])
            .do_update(set_={"role": role})
            .returning("team_id", "user_id", "role", "is_owner", "created_at", "updated_at"),
            schema_type=s.TeamMember,
        )

    async def remove_member(self, team_id: UUID, user_id: UUID) -> None:
        """Remove a user from a team."""
        await self.driver.execute(sql.delete("team_member").where_eq("team_id", team_id).where_eq("user_id", user_id))

    async def get_user_teams(self, user_id: UUID) -> list[s.Team]:
        """Get all teams for a user."""
        team_rows = await self.driver.select(
            sql.select("t.id")
            .from_("team t")
            .join("team_member tm", sql.raw("tm.team_id = t.id"))
            .where_eq("tm.user_id", user_id)
            .order_by(sql.column("t.name").asc())
        )
        return [await self._get_team_with_relationships(row["id"]) for row in team_rows]

    async def search_teams(self, query: str, limit: int = 10) -> list[s.Team]:
        """Search teams by name or description."""
        team_rows = await self.driver.select(
            sql.select("id")
            .from_("team")
            .where_ilike("name", f"%{query}%")
            .order_by(sql.column("name").asc())
            .limit(limit)
        )
        return [await self._get_team_with_relationships(row["id"]) for row in team_rows]

    @staticmethod
    def can_view_all(user: s.User) -> bool:
        """Check if user can view all teams."""
        if user.is_superuser:
            return True
        return any(role.name == SUPERUSER_ACCESS_ROLE for role in user.roles)

    async def _get_available_slug(self, name: str) -> str:
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
        return await self.exists(sql.select("1").from_("team").where_eq("slug", slug))

    async def _update_team_tags(self, team_id: UUID, tag_names: list[str]) -> None:
        """Update tags for a team."""
        await self.driver.execute(sql.delete("team_tag").where_eq("team_id", team_id))
        for tag_name in tag_names:
            tag_slug = slugify(tag_name)
            tag_row = await self.driver.select_one_or_none(
                sql.insert("tag")
                .values(name=tag_name, slug=tag_slug)
                .on_conflict(["name"])
                .do_nothing()
                .returning("id")
            )
            if not tag_row:
                tag_row = await self.driver.select_one(sql.select("id").from_("tag").where_eq("name", tag_name))
            await self.driver.execute(sql.insert("team_tag").values(team_id=team_id, tag_id=tag_row["id"]))

    async def _get_team_with_relationships(self, team_id: UUID) -> s.Team:
        """Get a team with all its relationships loaded."""
        team = await self.get_or_404(
            sql.select("id", "name", "description", "slug", "created_at", "updated_at")
            .from_("team")
            .where_eq("id", team_id),
            schema_type=s.Team,
            error_message=f"Team {team_id} not found",
        )
        members_data = await self.driver.select(
            sql.select(
                "tm.team_id",
                "tm.user_id",
                "tm.role",
                "tm.is_owner",
                "tm.created_at",
                "tm.updated_at",
                "u.id as user_id",
                "u.email as user_email",
                "u.name as user_name",
            )
            .from_("team_member tm")
            .join("user_account u", sql.raw("u.id = tm.user_id"))
            .where_eq("tm.team_id", team_id)
        )
        tags = await self.driver.select(
            sql.select("t.id", "t.slug", "t.name")
            .from_("tag t")
            .join("team_tag tt", sql.raw("tt.tag_id = t.id"))
            .where_eq("tt.team_id", team_id),
            schema_type=s.Tag,
        )
        team.members = [
            s.TeamMember(
                team_id=m["team_id"],
                user_id=m["user_id"],
                role=m["role"],
                is_owner=m["is_owner"],
                user=s.User(id=m["user_id"], email=m["user_email"], name=m["user_name"]),
            )
            for m in members_data
        ]
        team.tags = tags
        return team
