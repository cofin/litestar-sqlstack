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
            team_data["slug"] = await self.get_available_slug(team_data.get("name", ""))
        owner_id = team_data.pop("owner_id", None)
        tags = team_data.pop("tags", [])

        await self.driver.execute(
            sql.insert("team")
            .columns("id", "slug", "name", "description", "is_active", "created_at", "updated_at")
            .values(
                team_id,
                team_data["slug"],
                team_data["name"],
                team_data.get("description"),
                team_data.get("is_active", True),
                sql.raw("NOW()"),
                sql.raw("NOW()"),
            ),
        )

        if owner_id:
            await self.driver.execute(
                sql.insert("team_member")
                .columns("id", "team_id", "user_id", "role", "is_owner", "joined_at", "created_at", "updated_at")
                .values(
                    sql.raw("gen_random_uuid()"),
                    team_id,
                    owner_id,
                    "ADMIN",
                    True,
                    sql.raw("NOW()"),
                    sql.raw("NOW()"),
                    sql.raw("NOW()"),
                ),
            )
        await self._update_team_tags(team_id, tags)
        return await self._get_team_with_relationships(team_id)

    async def update(self, team_id: UUID, data: s.TeamUpdate) -> s.Team:
        """Update an existing team."""
        team_data = schema_dump(data, exclude_unset=True)
        if "name" in team_data and "slug" not in team_data:
            team_data["slug"] = await self.get_available_slug(team_data["name"])
        tags = team_data.pop("tags", None)

        if team_data:
            await self.driver.execute(
                sql.update("team").set(**team_data, updated_at=sql.raw("NOW()")).where_eq("id", team_id),
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
        if row := await self.driver.select_one_or_none(sql.select("id").from_("team").where_eq("slug", slug)):
            return await self._get_team_with_relationships(row["id"])
        return None

    async def list_with_count(self, *filters: StatementFilter, user: s.User | None = None) -> OffsetPagination[s.Team]:
        """List teams with pagination and filtering."""
        if user and not self.can_view_all(user):
            stmt = sql.select("DISTINCT t.id").from_("team t").join("team_member tm", "t.id = tm.team_id").where_eq("tm.user_id", user.id)
        else:
            stmt = sql.select("id").from_("team")

        data, total = await self.driver.select_with_total(stmt, *filters)
        limit_offset = self.driver.find_filter(LimitOffsetFilter, filters)
        teams = [await self._get_team_with_relationships(row["id"]) for row in data]
        return OffsetPagination(
            items=teams,
            limit=limit_offset.limit if limit_offset else 20,
            offset=limit_offset.offset if limit_offset else 0,
            total=total,
        )

    async def add_member(self, team_id: UUID, user_id: UUID, role: str = "MEMBER") -> s.TeamMember:
        """Add a user to a team."""
        # First insert the team member
        member = await self.driver.select_one(
            sql.insert("team_member")
            .columns("id", "team_id", "user_id", "role", "is_owner", "joined_at", "created_at", "updated_at")
            .values(
                sql.raw("gen_random_uuid()"),
                team_id,
                user_id,
                role,
                False,
                sql.raw("NOW()"),
                sql.raw("NOW()"),
                sql.raw("NOW()"),
            )
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

    async def remove_member(self, team_id: UUID, user_id: UUID) -> None:
        """Remove a user from a team."""
        await self.driver.execute(sql.delete("team_member").where_eq("team_id", team_id).where_eq("user_id", user_id))

    async def get_user_teams(self, user_id: UUID) -> list[s.Team]:
        """Get all teams for a user."""
        team_rows = await self.driver.select(
            sql.select("DISTINCT t.id")
            .from_("team t")
            .join("team_member tm", "t.id = tm.team_id")
            .where_eq("tm.user_id", user_id),
        )
        return [await self._get_team_with_relationships(row["id"]) for row in team_rows]

    async def search_teams(self, query: str, limit: int = 10) -> list[s.Team]:
        """Search teams by name or description."""
        team_rows = await self.driver.select(
            sql.select("id")
            .from_("team")
            .where("name ILIKE '%' || :query || '%' OR description ILIKE '%' || :query || '%'")
            .limit(limit),
            query=query,
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
        # Clear existing team tags
        await self.driver.execute(sql.delete("team_tag").where_eq("team_id", team_id))

        for tag_name in tag_names:
            tag_slug = slugify(tag_name)
            # Try to get or create tag
            tag_row = await self.driver.select_one_or_none(
                sql.select("id").from_("tag").where_eq("name", tag_name),
            )
            if not tag_row:
                # Create new tag
                tag_row = await self.driver.select_one(
                    sql.insert("tag")
                    .columns("id", "name", "slug", "created_at", "updated_at")
                    .values(sql.raw("gen_random_uuid()"), tag_name, tag_slug, sql.raw("NOW()"), sql.raw("NOW()"))
                    .returning("id"),
                )

            # Add team_tag relationship
            await self.driver.execute(
                sql.insert("team_tag")
                .columns("team_id", "tag_id")
                .values(team_id, tag_row["id"])
                .on_conflict_do_nothing(),
            )

    async def _get_team_with_relationships(self, team_id: UUID) -> s.Team:
        """Get a team with all its relationships loaded."""
        return await self.get_or_404(
            sql.select(
                "t.id",
                "t.slug",
                "t.name",
                "t.description",
                "t.is_active",
                "t.created_at",
                "t.updated_at",
                sql.raw("""
                    COALESCE(
                        json_agg(
                            DISTINCT jsonb_build_object(
                                'id', tm.id,
                                'userId', tm.user_id,
                                'email', u.email,
                                'name', u.name,
                                'role', tm.role,
                                'isOwner', tm.is_owner,
                                'joinedAt', tm.joined_at
                            )
                        ) FILTER (WHERE tm.id IS NOT NULL),
                        '[]'::json
                    ) as members
                """),
                sql.raw("""
                    COALESCE(
                        json_agg(
                            DISTINCT jsonb_build_object(
                                'id', tag.id,
                                'slug', tag.slug,
                                'name', tag.name,
                                'description', tag.description
                            )
                        ) FILTER (WHERE tag.id IS NOT NULL),
                        '[]'::json
                    ) as tags
                """),
            )
            .from_("team t")
            .left_join("team_member tm", "t.id = tm.team_id")
            .left_join("user_account u", "tm.user_id = u.id")
            .left_join("team_tag tt", "t.id = tt.team_id")
            .left_join("tag", "tt.tag_id = tag.id")
            .where_eq("t.id", team_id)
            .group_by("t.id", "t.slug", "t.name", "t.description", "t.is_active", "t.created_at", "t.updated_at"),
            schema_type=s.Team,
            error_message=f"Team {team_id} not found",
        )
