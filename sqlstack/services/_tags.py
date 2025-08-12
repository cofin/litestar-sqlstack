from __future__ import annotations

from typing import TYPE_CHECKING

from sqlspec import sql
from sqlspec.utils.text import slugify
from sqlspec.utils.type_guards import schema_dump

from sqlstack import schemas as s
from sqlstack.services._base import OffsetPagination, SQLSpecService, StatementFilter

if TYPE_CHECKING:
    from uuid import UUID


class TagService(SQLSpecService):
    """Handles database operations for tags using SQLSpec's sql builder API."""

    async def create(self, data: s.TagCreate) -> s.Tag:
        """Create a new tag with auto-generated slug."""
        tag_data = schema_dump(data, exclude_unset=True)
        if "slug" not in tag_data or not tag_data["slug"]:
            tag_data["slug"] = await self._get_available_slug(tag_data.get("name", ""))
        return await self.driver.select_one(
            sql.insert("tag").values(**tag_data).returning("id", "slug", "name"), schema_type=s.Tag
        )

    async def update(self, tag_id: UUID, data: s.TagUpdate) -> s.Tag:
        """Update an existing tag."""
        tag_data = schema_dump(data, exclude_unset=True)
        if "name" in tag_data and "slug" not in tag_data:
            tag_data["slug"] = await self._get_available_slug(tag_data["name"])
        return await self.driver.select_one(
            sql.update("tag").set(**tag_data).where_eq("id", tag_id).returning("id", "slug", "name"),
            schema_type=s.Tag,
        )

    async def delete(self, tag_id: UUID) -> s.Tag:
        """Delete a tag."""
        return await self.driver.select_one(
            sql.delete("tag").where_eq("id", tag_id).returning("id", "slug", "name"), schema_type=s.Tag
        )

    async def get_one(self, tag_id: UUID) -> s.Tag:
        """Get a single tag by ID."""
        return await self.get_or_404(
            sql.select("id", "slug", "name").from_("tag").where_eq("id", tag_id),
            schema_type=s.Tag,
            error_message=f"Tag {tag_id} not found",
        )

    async def get_by_slug(self, slug: str) -> s.Tag | None:
        """Get a tag by slug."""
        return await self.driver.select_one_or_none(
            sql.select("id", "slug", "name").from_("tag").where_eq("slug", slug), schema_type=s.Tag
        )

    async def get_by_name(self, name: str) -> s.Tag | None:
        """Get a tag by name."""
        return await self.driver.select_one_or_none(
            sql.select("id", "slug", "name").from_("tag").where_eq("name", name), schema_type=s.Tag
        )

    async def list_with_count(self, *filters: StatementFilter) -> OffsetPagination[s.Tag]:
        """List tags with pagination and filtering."""
        return await self.paginate(
            sql.select("id", "slug", "name").from_("tag").order_by(sql.column("name").asc()),
            *filters,
            schema_type=s.Tag,
        )

    async def upsert(self, data: s.TagCreate) -> s.Tag:
        """Create or update a tag by name."""
        # Try to get existing tag first
        existing = await self.get_by_name(data.name)
        if existing:
            return existing
        # Create new tag if it doesn't exist
        return await self.create(data)

    async def get_or_create(self, name: str, description: str | None = None) -> s.Tag:
        """Get an existing tag by name or create a new one."""
        if existing := await self.get_by_name(name):
            return existing
        return await self.create(s.TagCreate(name=name))

    async def search(self, query: str, limit: int = 10) -> list[s.Tag]:
        """Search tags by name or description."""
        return await self.driver.select(
            sql.select("id", "slug", "name")
            .from_("tag")
            .where_ilike("name", f"%{query}%")
            .order_by(sql.column("name").asc())
            .limit(limit),
            schema_type=s.Tag,
        )

    async def get_popular_tags(self, min_usage: int = 5, limit: int = 20) -> list[s.Tag]:
        """Get tags with high usage count."""
        # For now, return all tags ordered by name
        # TODO: Implement proper usage counting when team_tag relationships are available
        return await self.driver.select(
            sql.select("id", "slug", "name").from_("tag").order_by(sql.column("name").asc()).limit(limit),
            schema_type=s.Tag,
        )

    async def _get_available_slug(self, name: str) -> str:
        """Generate a unique slug for the given name."""
        base_slug = slugify(name)
        slug = base_slug
        counter = 1
        while await self._slug_exists(slug):
            slug = f"{base_slug}-{counter}"
            counter += 1
        return slug

    async def search_tags(self, query: str, limit: int = 10) -> list[s.Tag]:
        """Search tags by name (alias for search method)."""
        return await self.search(query, limit)

    async def _slug_exists(self, slug: str) -> bool:
        """Check if a slug already exists."""
        return await self.exists(sql.select("1").from_("tag").where_eq("slug", slug))
