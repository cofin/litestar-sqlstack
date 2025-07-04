from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

from sqlspec import sql
from sqlspec.statement.filters import LimitOffsetFilter
from sqlspec.typing import schema_dump
from sqlspec.utils.text import slugify
from uuid_utils.compat import uuid4

from sqlstack import schemas as s
from sqlstack.lib import constants
from sqlstack.services._base import AsyncpgService, OffsetPagination, StatementFilter

if TYPE_CHECKING:
    from collections.abc import Sequence


class TeamService(AsyncpgService):
    """Handles database operations for teams using SQLSpec's sql builder API.
    
    This service demonstrates best practices:
    - Using where_eq() and where_in() for clearer queries
    - Using built-in schema_type parameter instead of to_schema()
    - Using service helper methods instead of driver.execute()
    - Proper transaction handling with service methods
    - Complex relationship loading patterns
    """

    async def create(self, data: s.TeamCreate) -> s.Team:
        """Create a new team with owner and tags."""
        team_data = schema_dump(data, exclude_unset=True)
        
        # Generate ID and slug
        team_id = team_data.get("id", uuid4())
        team_data["id"] = team_id
        
        if "slug" not in team_data or not team_data["slug"]:
            team_data["slug"] = await self._get_available_slug(team_data.get("name", ""))
        
        # Extract owner and tags
        owner_id = team_data.pop("owner_id", None)
        tags = team_data.pop("tags", [])
        
        # Start transaction
        async with self.driver.transaction():
            # Create team
            stmt = (
                sql.insert("team")
                .values(**team_data)
                .returning("*")
            )
            team = await self.select_one(stmt, schema_type=s.Team)
            
            # Add owner as team member
            if owner_id:
                member_stmt = (
                    sql.insert("team_member")
                    .values(
                        team_id=team_id,
                        user_id=owner_id,
                        role="ADMIN",
                        is_owner=True
                    )
                )
                await self.execute(member_stmt)
            
            # Add tags
            await self._update_team_tags(team_id, tags)
            
            # Return complete team with relationships
            return await self._get_team_with_relationships(team_id)

    async def update(self, team_id: UUID, data: s.TeamUpdate) -> s.Team:
        """Update an existing team."""
        team_data = schema_dump(data, exclude_unset=True)
        
        # Regenerate slug if name changed but slug not provided
        if "name" in team_data and "slug" not in team_data:
            team_data["slug"] = await self._get_available_slug(team_data["name"])
        
        # Extract tags
        tags = team_data.pop("tags", None)
        
        async with self.driver.transaction():
            # Update team
            stmt = (
                sql.update("team")
                .set(**team_data)
                .where_eq("id", team_id)  # More readable!
                .returning("*")
            )
            team = await self.select_one(stmt, schema_type=s.Team)
            
            # Update tags if provided
            if tags is not None:
                await self._update_team_tags(team_id, tags)
            
            return await self._get_team_with_relationships(team_id)

    async def delete(self, team_id: UUID) -> s.Team:
        """Delete a team and all related data."""
        async with self.driver.transaction():
            # Get team for return
            team = await self._get_team_with_relationships(team_id)
            
            # Delete team (cascades to members, tags, etc.)
            stmt = sql.delete("team").where_eq("id", team_id)
            await self.execute(stmt)
            
            return team

    async def get_one(self, team_id: UUID) -> s.Team:
        """Get a single team by ID with all relationships."""
        return await self._get_team_with_relationships(team_id)

    async def get_by_slug(self, slug: str) -> s.Team | None:
        """Get a team by slug."""
        stmt = (
            sql.select("id")
            .from_("team")
            .where_eq("slug", slug)
        )
        row = await self.select_one_or_none(stmt)
        
        if row:
            return await self._get_team_with_relationships(row["id"])
        return None

    async def list(self, *filters: StatementFilter, user: s.User | None = None) -> OffsetPagination[s.Team]:
        """List teams with pagination and filtering.
        
        Demonstrates subquery patterns with WHERE IN.
        """
        # Build base query with user filtering
        stmt = sql.select("t.id").from_("team t")
        
        if user and not self.can_view_all(user):
            # User can only see teams they're a member of
            # Using subquery pattern
            member_subquery = (
                sql.select("team_id")
                .from_("team_member")
                .where_eq("user_id", user.id)
            )
            stmt = stmt.where_in("t.id", member_subquery)
        
        # Order by name
        stmt = stmt.order_by(sql.column("t.name").asc())
        
        # Get paginated team IDs
        # Using a custom approach since we need full objects
        # First get count
        count_stmt = stmt.with_only_select(sql.count())
        total = await self.select_value(count_stmt)
        
        # Then get paginated IDs
        limit_offset = next((f for f in filters if isinstance(f, LimitOffsetFilter)), LimitOffsetFilter(limit=20, offset=0))
        data_stmt = stmt.limit(limit_offset.limit).offset(limit_offset.offset)
        team_rows = await self.select(data_stmt)
        team_ids = [row["id"] for row in team_rows]
        
        # Get full team data with relationships
        teams = []
        for team_id in team_ids:
            team = await self._get_team_with_relationships(team_id)
            teams.append(team)
        
        return OffsetPagination(
            items=teams,
            limit=limit_offset.limit,
            offset=limit_offset.offset,
            total=total,
        )

    async def add_member(
        self, 
        team_id: UUID, 
        user_id: UUID, 
        role: str = "MEMBER"
    ) -> s.TeamMember:
        """Add a user to a team."""
        stmt = (
            sql.insert("team_member")
            .values(
                team_id=team_id,
                user_id=user_id,
                role=role,
                is_owner=False
            )
            .on_conflict(["team_id", "user_id"])
            .do_update(set_={"role": role})
            .returning("*")
        )
        return await self.select_one(stmt, schema_type=s.TeamMember)

    async def remove_member(self, team_id: UUID, user_id: UUID) -> None:
        """Remove a user from a team."""
        stmt = (
            sql.delete("team_member")
            .where_eq("team_id", team_id)
            .where_eq("user_id", user_id)  # Can chain where_eq!
        )
        await self.execute(stmt)

    async def get_user_teams(self, user_id: UUID) -> list[s.Team]:
        """Get all teams for a user."""
        stmt = (
            sql.select("t.id")
            .from_("team t")
            .join("team_member tm", sql.raw("tm.team_id = t.id"))
            .where_eq("tm.user_id", user_id)
            .order_by(sql.column("t.name").asc())
        )
        team_rows = await self.select(stmt)
        
        teams = []
        for row in team_rows:
            team = await self._get_team_with_relationships(row["id"])
            teams.append(team)
        
        return teams

    async def search_teams(self, query: str, limit: int = 10) -> list[s.Team]:
        """Search teams by name or description.
        
        Demonstrates using where_ilike for pattern matching.
        """
        stmt = (
            sql.select("id")
            .from_("team")
            .where_ilike("name", f"%{query}%")
            .order_by(sql.column("name").asc())
            .limit(limit)
        )
        team_rows = await self.select(stmt)
        
        teams = []
        for row in team_rows:
            team = await self._get_team_with_relationships(row["id"])
            teams.append(team)
        
        return teams

    @staticmethod
    def can_view_all(user: s.User) -> bool:
        """Check if user can view all teams."""
        if user.is_superuser:
            return True
        
        # Check if user has superuser role
        for role in user.roles:
            if role.name == constants.SUPERUSER_ACCESS_ROLE:
                return True
        
        return False

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
        # Use the exists helper method
        stmt = (
            sql.select("1")
            .from_("team")
            .where_eq("slug", slug)
        )
        return await self.exists(stmt)

    async def _update_team_tags(self, team_id: UUID, tag_names: list[str]) -> None:
        """Update tags for a team."""
        # Remove existing tags
        delete_stmt = sql.delete("team_tag").where_eq("team_id", team_id)
        await self.execute(delete_stmt)
        
        # Add new tags
        for tag_name in tag_names:
            # Get or create tag
            tag_slug = slugify(tag_name)
            tag_stmt = (
                sql.insert("tag")
                .values(name=tag_name, slug=tag_slug)
                .on_conflict(["name"])
                .do_nothing()
                .returning("id")
            )
            tag_row = await self.select_one_or_none(tag_stmt)
            
            if not tag_row:
                # Tag already exists, get its ID
                select_stmt = (
                    sql.select("id")
                    .from_("tag")
                    .where_eq("name", tag_name)
                )
                tag_row = await self.select_one(select_stmt)
            
            # Create team-tag relationship
            team_tag_stmt = (
                sql.insert("team_tag")
                .values(team_id=team_id, tag_id=tag_row["id"])
            )
            await self.execute(team_tag_stmt)

    async def _get_team_with_relationships(self, team_id: UUID) -> s.Team:
        """Get a team with all its relationships loaded.
        
        Demonstrates loading complex relationships with JOINs and multiple queries.
        """
        # Get team
        team_stmt = (
            sql.select("*")
            .from_("team")
            .where_eq("id", team_id)
        )
        team = await self.get_or_404(team_stmt, schema_type=s.Team, error_message=f"Team {team_id} not found")
        
        # Get members with user info using JOIN
        members_stmt = (
            sql.select(
                "tm.*",
                "u.id as user_id",
                "u.email as user_email",
                "u.name as user_name"
            )
            .from_("team_member tm")
            .join("user_account u", sql.raw("u.id = tm.user_id"))
            .where_eq("tm.team_id", team_id)
        )
        members_data = await self.select(members_stmt)
        
        # Get tags using JOIN
        tags_stmt = (
            sql.select("t.*")
            .from_("tag t")
            .join("team_tag tt", sql.raw("tt.tag_id = t.id"))
            .where_eq("tt.team_id", team_id)
        )
        tags = await self.select(tags_stmt, schema_type=s.Tag)
        
        # Construct team object with relationships
        # Note: In a real app, you might want to use a JOIN with schema_type
        # that handles nested relationships automatically
        team.members = [
            s.TeamMember(
                team_id=m["team_id"],
                user_id=m["user_id"],
                role=m["role"],
                is_owner=m["is_owner"],
                user=s.User(
                    id=m["user_id"],
                    email=m["user_email"],
                    name=m["user_name"]
                )
            )
            for m in members_data
        ]
        team.tags = tags
        
        return team