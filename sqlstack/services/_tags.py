from __future__ import annotations

from typing import TYPE_CHECKING

from sqlspec.utils.text import slugify
from sqlspec.utils.type_guards import schema_dump

from sqlstack import schemas as s
from sqlstack.config import db_manager
from sqlstack.services._base import OffsetPagination, SQLSpecService, StatementFilter

if TYPE_CHECKING:
    from uuid import UUID


class TagService(SQLSpecService):
    """Handles database operations for tags using SQLSpec's sql builder API."""

    async def create(self, data: s.TagCreate) -> s.Tag:
        """Create a new tag with auto-generated slug."""
        tag_data = schema_dump(data, exclude_unset=True)
        if "slug" not in tag_data or not tag_data["slug"]:
            tag_data["slug"] = await self.get_available_slug(tag_data.get("name", ""))
        return await self.driver.select_one(db_manager.get_sql("create-tag"), tag_data, schema_type=s.Tag)

    async def update(self, tag_id: UUID, data: s.TagUpdate) -> s.Tag:
        """Update an existing tag."""
        tag_data = schema_dump(data, exclude_unset=True)
        if "name" in tag_data and "slug" not in tag_data:
            tag_data["slug"] = await self.get_available_slug(tag_data["name"])
        tag_data["tag_id"] = tag_id
        return await self.driver.select_one(
            db_manager.get_sql("update-tag"),
            tag_data,
            schema_type=s.Tag,
        )

    async def delete(self, tag_id: UUID) -> s.Tag:
        """Delete a tag."""
        return await self.driver.select_one(db_manager.get_sql("delete-tag"), tag_id=tag_id, schema_type=s.Tag)

    async def get_one(self, tag_id: UUID) -> s.Tag:
        """Get a single tag by ID."""
        return await self.get_or_404(
            db_manager.get_sql("get-tag-by-id"),
            tag_id=tag_id,
            schema_type=s.Tag,
            error_message=f"Tag {tag_id} not found",
        )

    async def get_by_slug(self, slug: str) -> s.Tag | None:
        """Get a tag by slug."""
        return await self.driver.select_one_or_none(db_manager.get_sql("get-tag-by-slug"), slug=slug, schema_type=s.Tag)

    async def get_by_name(self, name: str) -> s.Tag | None:
        """Get a tag by name."""
        return await self.driver.select_one_or_none(
            db_manager.get_sql("get-tag-by-name"),
            name=name,
            schema_type=s.Tag,
        )

    async def list_with_count(self, *filters: StatementFilter) -> OffsetPagination[s.Tag]:
        """List tags with pagination and filtering."""
        return await self.paginate(
            db_manager.get_sql("list-tags"),
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
            db_manager.get_sql("search-tags"),
            query=query,
            limit=limit,
            schema_type=s.Tag,
        )

    async def get_popular_tags(self, min_usage: int = 5, limit: int = 20) -> list[s.Tag]:
        """Get tags with high usage count."""
        # FIXME: Usage counting not implemented yet - requires team_tag relationship table
        # Currently returns all tags ordered by name
        return await self.driver.select(
            db_manager.get_sql("get-popular-tags"),
            min_usage=min_usage,
            limit=limit,
            schema_type=s.Tag,
        )

    async def get_available_slug(self, name: str) -> str:
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
        return await self.exists(db_manager.get_sql("tag-exists-by-slug"), slug=slug)
