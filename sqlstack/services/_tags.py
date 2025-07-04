from __future__ import annotations

from uuid import UUID

from sqlspec import sql
from sqlspec.typing import schema_dump
from sqlspec.utils.text import slugify

from sqlstack import schemas as s
from sqlstack.services._base import AsyncpgService, OffsetPagination, StatementFilter


class TagService(AsyncpgService):
    """Handles database operations for tags using SQLSpec's sql builder API.

    This service demonstrates best practices:
    - Using where_eq() and where_ilike() for clearer queries
    - Using built-in schema_type parameter instead of to_schema()
    - Using service helper methods instead of driver.execute()
    - Using paginate() and exists() helpers
    """

    async def create(self, data: s.TagCreate) -> s.Tag:
        """Create a new tag with auto-generated slug."""
        tag_data = schema_dump(data, exclude_unset=True)

        # Auto-generate slug if not provided
        if "slug" not in tag_data or not tag_data["slug"]:
            tag_data["slug"] = await self._get_available_slug(tag_data.get("name", ""))

        stmt = sql.insert("tag").values(**tag_data).returning("*")
        # Use select_one with schema_type for automatic conversion
        return await self.select_one(stmt, schema_type=s.Tag)

    async def update(self, tag_id: UUID, data: s.TagUpdate) -> s.Tag:
        """Update an existing tag."""
        tag_data = schema_dump(data, exclude_unset=True)

        # Regenerate slug if name changed but slug not provided
        if "name" in tag_data and "slug" not in tag_data:
            tag_data["slug"] = await self._get_available_slug(tag_data["name"])

        stmt = (
            sql.update("tag")
            .set(**tag_data)
            .where_eq("id", tag_id)  # More readable than tuple syntax!
            .returning("*")
        )
        return await self.select_one(stmt, schema_type=s.Tag)

    async def delete(self, tag_id: UUID) -> s.Tag:
        """Delete a tag."""
        stmt = (
            sql.delete("tag")
            .where_eq("id", tag_id)  # Cleaner syntax
            .returning("*")
        )
        return await self.select_one(stmt, schema_type=s.Tag)

    async def get_one(self, tag_id: UUID) -> s.Tag:
        """Get a single tag by ID."""
        stmt = sql.select("*").from_("tag").where_eq("id", tag_id)
        # Using the get_or_404 helper for better error handling
        return await self.get_or_404(stmt, schema_type=s.Tag, error_message=f"Tag {tag_id} not found")

    async def get_by_slug(self, slug: str) -> s.Tag | None:
        """Get a tag by slug."""
        stmt = sql.select("*").from_("tag").where_eq("slug", slug)
        # Built-in schema conversion!
        return await self.select_one_or_none(stmt, schema_type=s.Tag)

    async def get_by_name(self, name: str) -> s.Tag | None:
        """Get a tag by name."""
        stmt = sql.select("*").from_("tag").where_eq("name", name)
        return await self.select_one_or_none(stmt, schema_type=s.Tag)

    async def list(self, *filters: StatementFilter) -> OffsetPagination[s.Tag]:
        """List tags with pagination and filtering."""
        stmt = sql.select("*").from_("tag").order_by(sql.column("name").asc())

        # Use the paginate helper method from base class
        return await self.paginate(stmt, *filters, schema_type=s.Tag)

    async def upsert(self, data: s.TagCreate) -> s.Tag:
        """Create or update a tag by name."""
        tag_data = schema_dump(data, exclude_unset=True)

        # Ensure we have a slug
        if "slug" not in tag_data or not tag_data["slug"]:
            tag_data["slug"] = await self._get_available_slug(tag_data.get("name", ""))

        stmt = sql.insert("tag").values(**tag_data).on_conflict(["name"]).do_update(set_=tag_data).returning("*")
        return await self.select_one(stmt, schema_type=s.Tag)

    async def get_or_create(self, name: str, description: str | None = None) -> s.Tag:
        """Get an existing tag by name or create a new one."""
        # First try to get existing
        existing = await self.get_by_name(name)
        if existing:
            return existing

        # Create new tag
        return await self.create(s.TagCreate(name=name, description=description))

    async def search(self, query: str, limit: int = 10) -> list[s.Tag]:
        """Search tags by name or description.

        Demonstrates using sql.raw() for complex WHERE conditions.
        """
        # Using sql.raw() with parameter binding for complex conditions
        stmt = (
            sql.select("*")
            .from_("tag")
            .where(
                sql.raw(
                    "(LOWER(name) LIKE LOWER(:pattern) OR LOWER(COALESCE(description, '')) LIKE LOWER(:pattern))",
                    pattern=f"%{query}%",
                )
            )
            .order_by(sql.column("name").asc())
            .limit(limit)
        )
        return await self.select(stmt, schema_type=s.Tag)

    async def get_popular_tags(self, min_usage: int = 5, limit: int = 20) -> list[s.Tag]:
        """Get tags with high usage count.

        Demonstrates using JOINs, GROUP BY, and HAVING with where_gte.
        """
        stmt = (
            sql.select("t.*", sql.raw("COUNT(it.item_id) as usage_count"))
            .from_("tag t")
            .left_join("item_tag it", sql.raw("it.tag_id = t.id"))
            .group_by(sql.raw("t.id"))
            .having(sql.raw("COUNT(it.item_id) >= :min_usage", min_usage=min_usage))
            .order_by(sql.raw("usage_count DESC"))
            .limit(limit)
        )
        return await self.select(stmt, schema_type=s.Tag)

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
        stmt = sql.select("1").from_("tag").where_eq("slug", slug)
        return await self.exists(stmt)
