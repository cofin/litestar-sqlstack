from __future__ import annotations

from uuid import UUID

from sqlspec import sql
from sqlspec.typing import schema_dump

from sqlstack import schemas
from sqlstack.services._base import AsyncpgService, OffsetPagination, StatementFilter


class RoleService(AsyncpgService):
    """Handles database operations for roles using SQLSpec's sql builder API.

    This service demonstrates best practices:
    - Using where_eq() instead of tuple syntax for clearer queries
    - Using built-in schema_type parameter instead of to_schema()
    - Using service helper methods instead of driver.execute()
    - Using paginate() helper for consistent pagination
    """

    async def create(self, data: schemas.RoleCreate) -> schemas.Role:
        """Create a new role."""
        stmt = sql.insert("role").values(**schema_dump(data, exclude_unset=True)).returning("*")
        # Use select_one with schema_type for automatic conversion
        return await self.select_one(stmt, schema_type=schemas.Role)

    async def update(self, role_id: UUID, data: schemas.RoleUpdate) -> schemas.Role:
        """Update an existing role."""
        return await self.execute(
            sql.update("role").set(**schema_dump(data, exclude_unset=True)).where_eq("id", role_id).returning("*"),
            schema_type=schemas.Role,
        )

    async def delete(self, role_id: UUID) -> schemas.Role:
        """Delete a role."""
        stmt = (
            sql.delete("role")
            .where_eq("id", role_id)  # Cleaner syntax
            .returning("*")
        )
        return await self.select_one(stmt, schema_type=schemas.Role)

    async def get_one(self, role_id: UUID) -> schemas.Role:
        """Get a single role by ID."""
        return await self.get_or_404(
            sql.select("*").from_("role").where_eq("id", role_id),
            schema_type=schemas.Role,
            error_message=f"Role {role_id} not found",
        )

    async def get_by_name(self, name: str) -> schemas.Role | None:
        """Get a role by name."""
        stmt = sql.select("*").from_("role").where_eq("name", name)
        # Built-in schema conversion!
        return await self.select_one_or_none(stmt, schema_type=schemas.Role)

    async def fetch_with_count(self, *filters: StatementFilter) -> OffsetPagination[schemas.Role]:
        """List roles with pagination and filtering."""
        stmt = sql.select("*").from_("role").order_by(sql.column("name").asc())

        # Use the paginate helper method from base class
        return await self.paginate(stmt, *filters, schema_type=schemas.Role)

    async def exists_by_name(self, name: str) -> bool:
        """Check if a role exists by name."""
        # Use the exists helper method
        stmt = sql.select("1").from_("role").where_eq("name", name)
        return await self.exists(stmt)

    async def get_default_role(self) -> schemas.Role:
        """Get the default user role."""
        stmt = sql.select("*").from_("role").where_eq("name", "User").limit(1)
        return await self.select_one(stmt, schema_type=schemas.Role)

    async def assign_role_to_user(self, user_id: UUID, role_id: UUID) -> None:
        """Assign a role to a user."""
        stmt = (
            sql.insert("user_role")
            .values(user_id=user_id, role_id=role_id, assigned_by_id=user_id)
            .on_conflict_do_nothing()
        )
        # For non-SELECT queries, we can use execute directly
        await self.execute(stmt)

    async def remove_role_from_user(self, user_id: UUID, role_id: UUID) -> None:
        """Remove a role from a user."""
        stmt = (
            sql.delete("user_role")
            .where_eq("user_id", user_id)
            .where_eq("role_id", role_id)  # Can chain multiple where_eq calls!
        )
        await self.execute(stmt)

    async def get_user_roles(self, user_id: UUID) -> list[schemas.Role]:
        """Get all roles for a user."""
        stmt = (
            sql.select("r.*")
            .from_("role r")
            .join("user_role ur", sql.raw("ur.role_id = r.id"))  # Use sql.raw() for join conditions
            .where_eq("ur.user_id", user_id)
            .order_by(sql.column("r.name").asc())
        )
        return await self.select(stmt, schema_type=schemas.Role)

    async def get_roles_by_permission(self, permission: str) -> list[schemas.Role]:
        """Get all roles that have a specific permission.

        Demonstrates using where_like for pattern matching.
        """
        stmt = (
            sql.select("*")
            .from_("role")
            .where_like("permissions", f"%{permission}%")  # Pattern matching
            .order_by(sql.column("name").asc())
        )
        return await self.select(stmt, schema_type=schemas.Role)

    async def get_active_roles(self, limit: int = 10) -> list[schemas.Role]:
        """Get most recently active roles.

        Demonstrates using multiple WHERE conditions and NOT NULL checks.
        """
        stmt = (
            sql.select("*")
            .from_("role")
            .where_eq("is_active", True)
            .where_is_not_null("last_used_at")
            .order_by(sql.column("last_used_at").desc())
            .limit(limit)
        )
        return await self.select(stmt, schema_type=schemas.Role)
