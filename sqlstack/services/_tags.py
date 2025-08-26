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

    async def create_tag(self, data: s.TagCreate) -> s.Tag:
        """Create a new tag with auto-generated slug."""
        tag_data = schema_dump(data, exclude_unset=True)
        if "slug" not in tag_data or not tag_data["slug"]:
            tag_data["slug"] = await self.get_available_slug(tag_data.get("name", ""))

        return await self.driver.select_one(
            sql.insert("tag")
            .columns("name", "description", "slug")
            .values(tag_data["name"], tag_data.get("description"), tag_data["slug"])
            .returning("id", "slug", "name", "description", "created_at", "updated_at"),
            schema_type=s.Tag,
        )

    async def update_tag(self, tag_id: UUID, data: s.TagUpdate) -> s.Tag:
        """Update an existing tag."""
        tag_data = schema_dump(data, exclude_unset=True)
        if "name" in tag_data and "slug" not in tag_data:
            tag_data["slug"] = await self.get_available_slug(tag_data["name"])

        if tag_data:
            await self.driver.execute(
                sql.update("tag").set(**tag_data).where_eq("id", tag_id),
            )

        return await self.driver.select_one(
            sql.select("id", "slug", "name", "description", "created_at", "updated_at")
            .from_("tag")
            .where_eq("id", tag_id),
            schema_type=s.Tag,
        )

    async def delete_tag(self, tag_id: UUID) -> None:
        """Delete a tag."""
        await self.driver.execute(sql.delete("tag").where_eq("id", tag_id))

    async def get_one(self, tag_id: UUID) -> s.Tag:
        """Get a single tag by ID."""
        return await self.get_or_404(
            sql.select("id", "slug", "name", "description", "created_at", "updated_at")
            .from_("tag")
            .where_eq("id", tag_id),
            error_message=f"Tag {tag_id} not found",
            schema_type=s.Tag,
        )

    async def list_with_count(self, *filters: StatementFilter) -> OffsetPagination[s.Tag]:
        """List tags with pagination and filtering."""
        base_query = sql.select("id", "slug", "name", "description", "created_at", "updated_at").from_("tag")
        return await self.paginate(
            base_query,
            *filters,
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

    async def _slug_exists(self, slug: str) -> bool:
        """Check if a slug already exists."""
        return await self.exists(sql.select("1").from_("tag").where_eq("slug", slug).limit(1))
