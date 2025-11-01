from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlspec import sql
from sqlspec.utils.text import slugify
from sqlspec.utils.type_guards import schema_dump

from sqlstack import schemas as s
from sqlstack.services import LimitOffsetFilter, OffsetPagination, SQLSpecService, StatementFilter

if TYPE_CHECKING:
    from collections.abc import Iterable


class TeamService(SQLSpecService):
    """Database operations for teams and their relationships."""

    async def create_team(self, data: s.TeamCreate, owner_id: UUID | None = None) -> s.Team:
        """Create a new team and optionally assign an owner."""

        payload = schema_dump(data, exclude_unset=True)
        team_id = uuid4()
        name = payload["name"]
        slug = await self.get_available_slug(name)
        tags = list(payload.pop("tags", []))

        await self.driver.execute(
            sql.insert("team")
            .columns("id", "slug", "name", "description", "is_active", "created_at", "updated_at")
            .values(
                team_id,
                slug,
                name,
                payload.get("description"),
                payload.get("is_active", True),
                sql.raw("NOW()"),
                sql.raw("NOW()"),
            )
        )

        if owner_id:
            await self.driver.execute(
                sql.insert("team_member")
                .columns("id", "team_id", "user_id", "role", "is_owner", "joined_at", "created_at", "updated_at")
                .values(
                    sql.raw("gen_random_uuid()"),
                    team_id,
                    owner_id,
                    s.TeamRoles.ADMIN.value,
                    True,
                    sql.raw("NOW()"),
                    sql.raw("NOW()"),
                    sql.raw("NOW()"),
                )
                .on_conflict_do_nothing()
            )

        if tags:
            await self._update_team_tags(team_id, tags)

        return await self.get_team(team_id)

    async def update_team(self, team_id: UUID, data: s.TeamUpdate) -> s.Team:
        """Update mutable team fields and relationships."""

        payload = schema_dump(data, exclude_unset=True)
        tags: Iterable[str] | None = payload.pop("tags", None)

        if "name" in payload and "slug" not in payload:
            payload["slug"] = await self.get_available_slug(payload["name"])

        if payload:
            await self.driver.execute(
                sql.update("team").set(**payload, updated_at=sql.raw("NOW()")).where_eq("id", team_id)
            )

        if tags is not None:
            await self._update_team_tags(team_id, list(tags))

        return await self.get_team(team_id)

    async def delete_team(self, team_id: UUID) -> None:
        """Delete a team and its relationships."""

        await self.get_team(team_id)
        await self.driver.execute(sql.delete("team").where_eq("id", team_id))

    async def get_team(self, team_id: UUID) -> s.Team:
        """Fetch a single team with members and tags."""

        return await self.get_or_404(
            self._team_with_relationships_statement().where_eq("t.id", team_id),
            schema_type=s.Team,
            error_message=f"Team {team_id} not found",
        )

    async def get_team_by_slug(self, slug: str) -> s.Team | None:
        """Fetch a team by slug with relationships."""

        statement = self._team_with_relationships_statement().where_eq("t.slug", slug)
        return await self.driver.select_one_or_none(statement, schema_type=s.Team)

    async def list_teams(
        self, *filters: StatementFilter, current_user: s.User | None = None
    ) -> OffsetPagination[s.Team]:
        """List teams applying filters and membership visibility rules."""

        if current_user and not self.can_view_all(current_user):
            base = (
                sql.select("DISTINCT team.id")
                .from_("team")
                .join("team_member", "team.id = team_member.team_id")
                .where_eq("team_member.user_id", current_user.id)
            )
        else:
            base = sql.select("team.id").from_("team")

        rows, total = await self.driver.select_with_total(base, *filters)
        limit_offset = self.driver.find_filter(LimitOffsetFilter, filters)
        teams = [await self.get_team(row["id"]) for row in rows]

        return OffsetPagination(
            items=teams,
            limit=limit_offset.limit if limit_offset else 20,
            offset=limit_offset.offset if limit_offset else 0,
            total=total,
        )

    async def add_member_to_team(
        self, team_id: UUID, user_id: UUID, role: s.TeamRoles | str = s.TeamRoles.MEMBER
    ) -> s.TeamMember:
        """Add a user to a team and return the membership record."""

        role_value = role.value if isinstance(role, s.TeamRoles) else role
        await self.driver.execute(
            sql.insert("team_member")
            .columns("id", "team_id", "user_id", "role", "is_owner", "joined_at", "created_at", "updated_at")
            .values(
                sql.raw("gen_random_uuid()"),
                team_id,
                user_id,
                role_value,
                False,
                sql.raw("NOW()"),
                sql.raw("NOW()"),
                sql.raw("NOW()"),
            )
        )

        return await self.driver.select_one(
            self._team_member_statement().where_eq("tm.team_id", team_id).where_eq("tm.user_id", user_id),
            schema_type=s.TeamMember,
        )

    async def remove_member_from_team(self, team_id: UUID, user_id: UUID) -> None:
        """Remove a user from a team."""

        await self.driver.execute(sql.delete("team_member").where_eq("team_id", team_id).where_eq("user_id", user_id))

    async def get_user_teams(self, user_id: UUID) -> list[s.Team]:
        """Return all teams for a given user."""

        rows = await self.driver.select(
            sql.select("DISTINCT t.slug")
            .from_("team t")
            .join("team_member tm", "t.id = tm.team_id")
            .where_eq("tm.user_id", user_id)
        )
        teams: list[s.Team] = []
        for row in rows:
            slug = row.get("slug")
            if not slug:
                continue
            team = await self.get_team_by_slug(slug)
            if team:
                teams.append(team)
        return teams

    async def search_teams(self, query: str, limit: int = 10) -> list[s.Team]:
        """Search teams by name or description."""

        rows = await self.driver.select(
            sql.select("id")
            .from_("team")
            .where("name ILIKE '%' || :query || '%' OR description ILIKE '%' || :query || '%'")
            .limit(limit),
            query=query,
        )
        return [await self.get_team(row["id"]) for row in rows]

    @staticmethod
    def can_view_all(user: s.User) -> bool:
        """Return True if the user can view all teams."""

        return any(role.role_slug == "superuser" for role in user.roles)

    async def get_available_slug(self, name: str) -> str:
        """Generate a unique slug for a team name."""

        base = slugify(name)
        slug = base
        counter = 1
        while await self._slug_exists(slug):
            slug = f"{base}-{counter}"
            counter += 1
        return slug

    async def _slug_exists(self, slug: str) -> bool:
        return await self.exists(sql.select("1").from_("team").where_eq("slug", slug))

    async def _update_team_tags(self, team_id: UUID, tag_names: list[str]) -> None:
        await self.driver.execute(sql.delete("team_tag").where_eq("team_id", team_id))

        for tag_name in tag_names:
            tag_slug = slugify(tag_name)
            tag_row = await self.driver.select_one_or_none(sql.select("id").from_("tag").where_eq("name", tag_name))
            if not tag_row:
                tag_row = await self.driver.select_one(
                    sql.insert("tag")
                    .columns("id", "name", "slug", "created_at", "updated_at")
                    .values(sql.raw("gen_random_uuid()"), tag_name, tag_slug, sql.raw("NOW()"), sql.raw("NOW()"))
                    .returning("id")
                )

            await self.driver.execute(
                sql.insert("team_tag")
                .columns("team_id", "tag_id")
                .values(team_id, tag_row["id"])
                .on_conflict_do_nothing()
            )

    @staticmethod
    def _team_member_statement():  # noqa: ANN205 - dynamic query builder
        return (
            sql.select(
                "tm.id", "tm.team_id", "tm.user_id", "u.email", "u.name", "tm.role", "tm.is_owner", "tm.joined_at"
            )
            .from_("team_member tm")
            .join("user_account u", "tm.user_id = u.id")
        )

    @staticmethod
    def _team_with_relationships_statement():  # noqa: ANN205 - dynamic query builder
        return (
            sql.select(
                "t.id",
                "t.slug",
                "t.name",
                "t.description",
                "t.is_active",
                "t.created_at",
                "t.updated_at",
                sql.raw(
                    """
                    COALESCE(
                        json_agg(
                            DISTINCT jsonb_build_object(
                                'id', tm.id,
                                'teamId', tm.team_id,
                                'userId', tm.user_id,
                                'email', u.email,
                                'name', u.name,
                                'role', tm.role,
                                'isOwner', tm.is_owner,
                                'joinedAt', tm.joined_at
                            )
                        ) FILTER (WHERE tm.id IS NOT NULL),
                        '[]'::json
                    ) AS members
                    """
                ),
                sql.raw(
                    """
                    COALESCE(
                        json_agg(
                            DISTINCT jsonb_build_object(
                                'id', tag.id,
                                'slug', tag.slug,
                                'name', tag.name
                            )
                        ) FILTER (WHERE tag.id IS NOT NULL),
                        '[]'::json
                    ) AS tags
                    """
                ),
            )
            .from_("team t")
            .left_join("team_member tm", "t.id = tm.team_id")
            .left_join("user_account u", "tm.user_id = u.id")
            .left_join("team_tag tt", "t.id = tt.team_id")
            .left_join("tag", "tt.tag_id = tag.id")
            .group_by("t.id", "t.slug", "t.name", "t.description", "t.is_active", "t.created_at", "t.updated_at")
        )
