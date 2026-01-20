from __future__ import annotations

from typing import TYPE_CHECKING

from sqlspec import sql

from sqlstack.domain.accounts import schemas as s
from sqlstack.lib.service import OffsetPagination, SQLSpecAsyncService, StatementFilter

if TYPE_CHECKING:
    from uuid import UUID

__all__ = ["UserRoleService"]


class UserRoleService(SQLSpecAsyncService):
    """Handles database operations for user roles and role assignments."""

    async def assign_role_to_user(self, user_id: UUID, role_id: UUID) -> s.UserRole:
        """Assign a role to a user."""
        # Insert the role assignment
        await self.driver.execute(
            sql
            .insert("user_account_role")
            .columns("id", "user_id", "role_id", "assigned_at", "created_at", "updated_at")
            .values(
                sql.raw("gen_random_uuid()"), user_id, role_id, sql.raw("NOW()"), sql.raw("NOW()"), sql.raw("NOW()")
            )
        )
        # Return the full UserRole with role details
        return await self.driver.select_one(
            sql
            .select("ur.user_id", "ur.role_id", "ur.assigned_at", "r.slug as role_slug", "r.name as role_name")
            .from_("user_account_role ur")
            .join("role r", "ur.role_id = r.id")
            .where_eq("ur.user_id", user_id)
            .where_eq("ur.role_id", role_id),
            schema_type=s.UserRole,
        )

    async def revoke_role_from_user(self, user_id: UUID, role_id: UUID) -> None:
        """Revoke a role from a user."""
        await self.driver.execute(
            sql.delete("user_account_role").where_eq("user_id", user_id).where_eq("role_id", role_id)
        )

    async def get_user_roles(self, user_id: UUID) -> list[s.UserRole]:
        """Get all roles assigned to a user."""
        return await self.driver.select(
            sql
            .select(
                "ur.user_id",
                "ur.role_id",
                "ur.assigned_at",
                "ur.assigned_by_id",
                "r.slug as role_slug",
                "r.name as role_name",
            )
            .from_("user_account_role ur")
            .join("role r", "ur.role_id = r.id")
            .where_eq("ur.user_id", user_id)
            .order_by("r.name"),
            schema_type=s.UserRole,
        )

    async def get_role_users(self, role_id: UUID) -> list[s.User]:
        """Get all users assigned to a specific role."""
        return await self.driver.select(
            sql
            .select(
                "u.id",
                "u.email",
                "u.name",
                "u.is_superuser",
                "u.is_active",
                "u.is_verified",
                "u.password_hash",
                "u.avatar_url",
                "u.created_at",
                "u.updated_at",
                "u.last_login",
            )
            .from_("user_account u")
            .join("user_account_role ur", "u.id = ur.user_id")
            .where_eq("ur.role_id", role_id)
            .order_by("u.name"),
            schema_type=s.User,
        )

    async def user_has_role(self, user_id: UUID, role_id: UUID) -> bool:
        """Check if a user has a specific role."""
        return await self.exists(
            sql.select("1").from_("user_account_role").where_eq("user_id", user_id).where_eq("role_id", role_id)
        )

    async def user_has_role_by_slug(self, user_id: UUID, role_slug: str) -> bool:
        """Check if a user has a role by role slug."""
        return await self.exists(
            sql
            .select("1")
            .from_("user_account_role ur")
            .join("role r", "ur.role_id = r.id")
            .where_eq("ur.user_id", user_id)
            .where_eq("r.slug", role_slug)
        )

    async def get_users_by_role_slug(self, role_slug: str) -> list[s.User]:
        """Get all users with a specific role by role slug."""
        return await self.driver.select(
            sql
            .select(
                "u.id",
                "u.email",
                "u.name",
                "u.is_superuser",
                "u.is_active",
                "u.is_verified",
                "u.password_hash",
                "u.avatar_url",
                "u.created_at",
                "u.updated_at",
                "u.last_login",
            )
            .from_("user_account u")
            .join("user_account_role ur", "u.id = ur.user_id")
            .join("role r", "ur.role_id = r.id")
            .where_eq("r.slug", role_slug)
            .order_by("u.name"),
            schema_type=s.User,
        )

    async def list_all_assignments(self, *filters: StatementFilter) -> OffsetPagination[s.UserRole]:
        """List all user-role assignments with pagination."""
        return await self.paginate(
            sql
            .select(
                "ur.user_id",
                "ur.role_id",
                "ur.assigned_at",
                "ur.assigned_by_id",
                "r.slug as role_slug",
                "r.name as role_name",
                "u.email",
                "u.name as user_name",
            )
            .from_("user_account_role ur")
            .join("role r", "ur.role_id = r.id")
            .join("user_account u", "ur.user_id = u.id")
            .order_by("ur.assigned_at DESC"),
            *filters,
            schema_type=s.UserRole,
        )

    async def get_role_assignment_count(self, role_id: UUID) -> int:
        """Get the number of users assigned to a role."""
        result = await self.driver.select_one(
            sql.select("COUNT(*) as count").from_("user_account_role").where_eq("role_id", role_id)
        )
        return int(result["count"])

    async def get_user_assignment_count(self, user_id: UUID) -> int:
        """Get the number of roles assigned to a user."""
        result = await self.driver.select_one(
            sql.select("COUNT(*) as count").from_("user_account_role").where_eq("user_id", user_id)
        )
        return int(result["count"])

    async def bulk_assign_role(self, role_id: UUID, user_ids: list[UUID]) -> list[s.UserRole]:
        """Assign a role to multiple users."""
        assignments: list[s.UserRole] = []
        for user_id in user_ids:
            assignment = await self.assign_role_to_user(user_id, role_id)
            assignments.append(assignment)
        return assignments

    async def bulk_revoke_role(self, role_id: UUID, user_ids: list[UUID]) -> None:
        """Revoke a role from multiple users."""
        await self.driver.execute(sql.delete("user_role").where_eq("role_id", role_id).where_in("user_id", user_ids))
