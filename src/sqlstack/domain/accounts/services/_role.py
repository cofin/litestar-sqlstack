from __future__ import annotations

from typing import TYPE_CHECKING

from sqlspec import sql
from sqlspec.utils.serializers import schema_dump
from sqlspec.utils.text import slugify

from sqlstack.domain.accounts import schemas as s
from sqlstack.lib.service import OffsetPagination, SQLSpecAsyncService, StatementFilter

if TYPE_CHECKING:
    from uuid import UUID


class RoleService(SQLSpecAsyncService):
    """Handles database operations for roles using SQLSpec's sql builder API."""

    async def create_role(self, data: s.RoleCreate) -> s.Role:
        """Create a new role."""
        role_data = schema_dump(data, exclude_unset=True)
        if "slug" not in role_data:
            role_data["slug"] = await self.get_available_slug(role_data["name"])

        return await self.driver.select_one(
            sql
            .insert("role")
            .columns("id", "slug", "name", "description", "created_at", "updated_at")
            .values(
                sql.raw("gen_random_uuid()"),
                role_data["slug"],
                role_data["name"],
                role_data.get("description"),
                sql.raw("NOW()"),
                sql.raw("NOW()"),
            )
            .returning("id", "slug", "name", "description", "created_at", "updated_at"),
            schema_type=s.Role,
        )

    async def update_role(self, role_id: UUID, data: s.RoleUpdate) -> s.Role:
        """Update an existing role."""
        update_data = schema_dump(data, exclude_unset=True)
        if update_data:
            await self.driver.execute(sql.update("role").set(**update_data).where_eq("id", role_id))
        return await self.driver.select_one(
            sql
            .select("id", "slug", "name", "description", "created_at", "updated_at")
            .from_("role")
            .where_eq("id", role_id),
            schema_type=s.Role,
        )

    async def delete(self, role_id: UUID) -> s.Role:
        """Delete a role."""
        role = await self.get_one(role_id)
        await self.driver.execute(sql.delete("role").where_eq("id", role_id))
        return role

    async def get_one(self, role_id: UUID) -> s.Role:
        """Get a single role by ID."""
        return await self.get_or_404(
            sql
            .select("id", "slug", "name", "description", "created_at", "updated_at")
            .from_("role")
            .where_eq("id", role_id),
            error_message=f"Role {role_id} not found",
            schema_type=s.Role,
        )

    async def get_by_name(self, name: str) -> s.Role | None:
        """Get a role by name."""
        return await self.driver.select_one_or_none(
            sql
            .select("id", "slug", "name", "description", "created_at", "updated_at")
            .from_("role")
            .where_eq("name", name),
            schema_type=s.Role,
        )

    async def fetch_with_count(self, *filters: StatementFilter) -> OffsetPagination[s.Role]:
        """List roles with pagination and filtering."""
        base_query = (
            sql
            .select("id", "slug", "name", "description", "created_at", "updated_at")
            .from_("role")
            .order_by("created_at", "DESC")
        )
        return await self.paginate(base_query, *filters, schema_type=s.Role)

    async def exists_by_name(self, name: str) -> bool:
        """Check if a role exists by name."""
        return await self.exists(sql.select("1").from_("role").where_eq("name", name).limit(1))

    async def get_default_role(self) -> s.Role:
        """Get the default user role."""
        return await self.driver.select_one(
            sql
            .select("id", "slug", "name", "description", "created_at", "updated_at")
            .from_("role")
            .where_eq("slug", "member")
            .limit(1),
            schema_type=s.Role,
        )

    async def assign_role_to_user(self, user_id: UUID, role_id: UUID) -> None:
        """Assign a role to a user."""
        await self.driver.execute(
            sql
            .insert("user_account_role")
            .columns("id", "user_id", "role_id", "assigned_at", "created_at", "updated_at")
            .values(
                sql.raw("gen_random_uuid()"), user_id, role_id, sql.raw("NOW()"), sql.raw("NOW()"), sql.raw("NOW()")
            )
            .on_conflict_do_nothing()
        )

    async def remove_role_from_user(self, user_id: UUID, role_id: UUID) -> None:
        """Remove a role from a user."""
        await self.driver.execute(
            sql.delete("user_account_role").where_eq("user_id", user_id).where_eq("role_id", role_id)
        )

    async def get_user_roles(self, user_id: UUID) -> list[s.Role]:
        """Get all roles for a user."""
        return await self.driver.select(
            sql
            .select("r.id", "r.slug", "r.name", "r.description", "r.created_at", "r.updated_at")
            .from_("role r")
            .join("user_account_role ur", "r.id = ur.role_id")
            .where_eq("ur.user_id", user_id)
            .order_by("r.name"),
            schema_type=s.Role,
        )

    async def get_roles_by_permission(self, permission: str) -> list[s.Role]:
        """Get all roles that have a specific permission."""
        # Note: Permissions system not implemented yet
        return []

    async def get_active_roles(self, limit: int = 10) -> list[s.Role]:
        """Get most recently active roles."""
        return await self.driver.select(
            sql
            .select("id", "slug", "name", "description", "created_at", "updated_at")
            .from_("role")
            .order_by("updated_at", "DESC")
            .limit(limit),
            schema_type=s.Role,
        )

    async def list_with_count(self, *filters: StatementFilter) -> OffsetPagination[s.Role]:
        """List roles with pagination and filtering (alias for fetch_with_count)."""
        return await self.fetch_with_count(*filters)

    async def get_by_slug(self, slug: str) -> s.Role | None:
        """Get a role by slug."""
        return await self.driver.select_one_or_none(
            sql
            .select("id", "slug", "name", "description", "created_at", "updated_at")
            .from_("role")
            .where_eq("slug", slug),
            schema_type=s.Role,
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
        return await self.exists(sql.select("1").from_("role").where_eq("slug", slug).limit(1))

    async def ensure_default_roles(self) -> None:
        """Ensure default roles exist."""
        # Check if User role exists
        if not await self.exists_by_name("User"):
            await self.create_role(s.RoleCreate(name="User"))

        # Check if Superuser role exists
        if not await self.exists_by_name("Superuser"):
            await self.create_role(s.RoleCreate(name="Superuser"))
