from __future__ import annotations

from typing import TYPE_CHECKING

from sqlspec import sql
from sqlspec.utils.type_guards import schema_dump

from sqlstack import schemas
from sqlstack.services._base import OffsetPagination, SQLSpecService, StatementFilter

if TYPE_CHECKING:
    from uuid import UUID


class RoleService(SQLSpecService):
    """Handles database operations for roles using SQLSpec's sql builder API."""

    async def create(self, data: schemas.RoleCreate) -> schemas.Role:
        """Create a new role."""
        role_data = schema_dump(data, exclude_unset=True)
        # Auto-generate slug from name if not provided
        if "slug" not in role_data:
            role_data["slug"] = role_data["name"].lower().replace(" ", "-")

        return await self.driver.select_one(
            sql.insert("role").values_from_dict(role_data).returning("id", "slug", "name", "created_at", "updated_at"),
            schema_type=schemas.Role,
        )

    async def update(self, role_id: UUID, data: schemas.RoleUpdate) -> schemas.Role:
        """Update an existing role."""
        update_data = schema_dump(data, exclude_unset=True)
        return await self.driver.select_one(
            sql.update("role")
            .set(update_data)
            .where_eq("id", role_id)
            .returning("id", "slug", "name", "created_at", "updated_at"),
            schema_type=schemas.Role,
        )

    async def delete(self, role_id: UUID) -> schemas.Role:
        """Delete a role."""
        return await self.driver.select_one(
            sql.delete("role").where_eq("id", role_id).returning("id", "slug", "name", "created_at", "updated_at"),
            schema_type=schemas.Role,
        )

    async def get_one(self, role_id: UUID) -> schemas.Role:
        """Get a single role by ID."""
        return await self.driver.select_one(
            sql.select("id", "slug", "name", "created_at", "updated_at").from_("role").where_eq("id", role_id),
            schema_type=schemas.Role,
        )

    async def get_by_name(self, name: str) -> schemas.Role | None:
        """Get a role by name."""
        return await self.driver.select_one_or_none(
            sql.select("id", "slug", "name", "created_at", "updated_at").from_("role").where_eq("name", name),
            schema_type=schemas.Role,
        )

    async def fetch_with_count(self, *filters: StatementFilter) -> OffsetPagination[schemas.Role]:
        """List roles with pagination and filtering."""
        return await self.paginate(
            sql.select("id", "slug", "name", "created_at", "updated_at")
            .from_("role")
            .order_by(sql.column("name").asc()),
            *filters,
            schema_type=schemas.Role,
        )

    async def exists_by_name(self, name: str) -> bool:
        """Check if a role exists by name."""
        row_exists = await self.driver.select_value_or_none(sql.select("1").from_("role").where_eq("name", name))
        return row_exists is not None

    async def get_default_role(self) -> schemas.Role:
        """Get the default user role."""
        return await self.driver.select_one(
            sql.select("id", "slug", "name", "created_at", "updated_at")
            .from_("role")
            .where_eq("name", "User")
            .limit(1),
            schema_type=schemas.Role,
        )

    async def assign_role_to_user(self, user_id: UUID, role_id: UUID) -> None:
        """Assign a role to a user."""
        await self.driver.execute(
            sql.insert("user_role")
            .values_from_dict({"user_id": user_id, "role_id": role_id, "assigned_by_id": user_id})
            .on_conflict_do_nothing()
        )

    async def remove_role_from_user(self, user_id: UUID, role_id: UUID) -> None:
        """Remove a role from a user."""
        await self.driver.execute(sql.delete("user_role").where_eq("user_id", user_id).where_eq("role_id", role_id))

    async def get_user_roles(self, user_id: UUID) -> list[schemas.Role]:
        """Get all roles for a user."""
        return await self.driver.select(
            sql.select("r.id", "r.slug", "r.name", "r.created_at", "r.updated_at")
            .from_("role r")
            .join("user_role ur", on="ur.role_id = r.id")
            .where_eq("ur.user_id", user_id)
            .order_by(sql.column("r.name").asc()),
            schema_type=schemas.Role,
        )

    async def get_roles_by_permission(self, permission: str) -> list[schemas.Role]:
        """Get all roles that have a specific permission."""
        return await self.driver.select(
            sql.select("id", "slug", "name", "created_at", "updated_at")
            .from_("role")
            .where_like("permissions", f"%{permission}%")
            .order_by(sql.column("name").asc()),
            schema_type=schemas.Role,
        )

    async def get_active_roles(self, limit: int = 10) -> list[schemas.Role]:
        """Get most recently active roles."""
        return await self.driver.select(
            sql.select("id", "slug", "name", "created_at", "updated_at")
            .from_("role")
            .where_eq("is_active", True)
            .where_is_not_null("last_used_at")
            .order_by(sql.column("last_used_at").desc())
            .limit(limit),
            schema_type=schemas.Role,
        )

    async def list_with_count(self, *filters: StatementFilter) -> OffsetPagination[schemas.Role]:
        """List roles with pagination and filtering (alias for fetch_with_count)."""
        return await self.fetch_with_count(*filters)

    async def get_by_slug(self, slug: str) -> schemas.Role | None:
        """Get a role by slug."""
        return await self.driver.select_one_or_none(
            sql.select("id", "slug", "name", "created_at", "updated_at").from_("role").where_eq("slug", slug),
            schema_type=schemas.Role,
        )

    async def ensure_default_roles(self) -> None:
        """Ensure default roles exist."""
        # Check if User role exists
        if not await self.exists_by_name("User"):
            await self.create(schemas.RoleCreate(name="User"))

        # Check if Superuser role exists
        if not await self.exists_by_name("Superuser"):
            await self.create(schemas.RoleCreate(name="Superuser"))
