from __future__ import annotations

from typing import TYPE_CHECKING

from sqlspec.utils.text import slugify
from sqlspec.utils.type_guards import schema_dump

from sqlstack import schemas as s
from sqlstack.config import sqlspec as db_manager
from sqlstack.services._base import OffsetPagination, SQLSpecService, StatementFilter

if TYPE_CHECKING:
    from uuid import UUID


class RoleService(SQLSpecService):
    """Handles database operations for roles using SQLSpec's sql builder API."""

    async def create_role(self, data: s.RoleCreate) -> s.Role:
        """Create a new role."""
        role_data = schema_dump(data, exclude_unset=True)
        if "slug" not in role_data:
            role_data["slug"] = await self.get_available_slug(role_data["name"])

        return await self.driver.select_one(db_manager.get_sql("create-role"), role_data, schema_type=s.Role)

    async def update_role(self, role_id: UUID, data: s.RoleUpdate) -> s.Role:
        """Update an existing role."""
        update_data = schema_dump(data, exclude_unset=True)
        update_data["role_id"] = role_id
        return await self.driver.select_one(db_manager.get_sql("update-role"), update_data, schema_type=s.Role)

    async def delete(self, role_id: UUID) -> s.Role:
        """Delete a role."""
        return await self.driver.select_one(
            db_manager.get_sql("delete-role"),
            role_id=role_id,
            schema_type=s.Role,
        )

    async def get_one(self, role_id: UUID) -> s.Role:
        """Get a single role by ID."""
        return await self.driver.select_one(
            db_manager.get_sql("get-role-by-id"),
            role_id=role_id,
            schema_type=s.Role,
        )

    async def get_by_name(self, name: str) -> s.Role | None:
        """Get a role by name."""
        return await self.driver.select_one_or_none(
            db_manager.get_sql("get-role-by-name"),
            name=name,
            schema_type=s.Role,
        )

    async def fetch_with_count(self, *filters: StatementFilter) -> OffsetPagination[s.Role]:
        """List roles with pagination and filtering."""
        return await self.paginate(db_manager.get_sql("list-roles"), *filters, schema_type=s.Role)

    async def exists_by_name(self, name: str) -> bool:
        """Check if a role exists by name."""
        return await self.exists(db_manager.get_sql("role-exists-by-name"), name=name)

    async def get_default_role(self) -> s.Role:
        """Get the default user role."""
        return await self.driver.select_one(db_manager.get_sql("get-default-user-role"), schema_type=s.Role)

    async def assign_role_to_user(self, user_id: UUID, role_id: UUID) -> None:
        """Assign a role to a user."""
        await self.driver.execute(db_manager.get_sql("assign-role-to-user"), user_id=user_id, role_id=role_id)

    async def remove_role_from_user(self, user_id: UUID, role_id: UUID) -> None:
        """Remove a role from a user."""
        await self.driver.execute(db_manager.get_sql("remove-role-from-user"), user_id=user_id, role_id=role_id)

    async def get_user_roles(self, user_id: UUID) -> list[s.Role]:
        """Get all roles for a user."""
        return await self.driver.select(
            db_manager.get_sql("get-user-roles"),
            user_id=user_id,
            schema_type=s.Role,
        )

    async def get_roles_by_permission(self, permission: str) -> list[s.Role]:
        """Get all roles that have a specific permission."""
        return await self.driver.select(
            db_manager.get_sql("get-roles-by-permission"),
            permission=permission,
            schema_type=s.Role,
        )

    async def get_active_roles(self, limit: int = 10) -> list[s.Role]:
        """Get most recently active roles."""
        return await self.driver.select(db_manager.get_sql("get-active-roles"), limit=limit, schema_type=s.Role)

    async def list_with_count(self, *filters: StatementFilter) -> OffsetPagination[s.Role]:
        """List roles with pagination and filtering (alias for fetch_with_count)."""
        return await self.fetch_with_count(*filters)

    async def get_by_slug(self, slug: str) -> s.Role | None:
        """Get a role by slug."""
        return await self.driver.select_one_or_none(
            db_manager.get_sql("get-role-by-slug"),
            slug=slug,
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
        return await self.exists(db_manager.get_sql("role-exists-by-slug"), slug=slug)

    async def ensure_default_roles(self) -> None:
        """Ensure default roles exist."""
        # Check if User role exists
        if not await self.exists_by_name("User"):
            await self.create_role(s.RoleCreate(name="User"))

        # Check if Superuser role exists
        if not await self.exists_by_name("Superuser"):
            await self.create_role(s.RoleCreate(name="Superuser"))
