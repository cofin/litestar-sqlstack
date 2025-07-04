from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

from sqlspec import sql
from sqlspec.statement.filters import LimitOffsetFilter
from sqlspec.typing import schema_dump

from sqlstack import schemas as s
from sqlstack.services._base import AsyncpgService, OffsetPagination, StatementFilter

if TYPE_CHECKING:
    from collections.abc import Sequence


class UserService(AsyncpgService):
    """Handles database operations for users using SQLSpec's sql builder API.
    
    This service demonstrates best practices:
    - Using where_eq() instead of tuple syntax
    - Using built-in schema_type parameter instead of to_schema()
    - Using service helper methods instead of driver.execute()
    - Using paginate() helper for consistent pagination
    """

    async def create(self, data: s.UserCreate) -> s.User:
        """Create a new user account."""
        stmt = (
            sql.insert("user_account")
            .values(**schema_dump(data, exclude_unset=True))
            .returning("*")
        )
        # Use select_one with schema_type for automatic conversion
        return await self.select_one(stmt, schema_type=s.User)

    async def update(self, item_id: UUID, data: s.UserUpdate) -> s.User:
        """Update an existing user account."""
        stmt = (
            sql.update("user_account")
            .set(**schema_dump(data, exclude_unset=True))
            .where_eq("id", item_id)  # More readable than tuple syntax!
            .returning("*")
        )
        return await self.select_one(stmt, schema_type=s.User)

    async def delete(self, item_id: UUID) -> s.User:
        """Delete a user account."""
        stmt = (
            sql.delete("user_account")
            .where_eq("id", item_id)  # Cleaner syntax
            .returning("*")
        )
        return await self.select_one(stmt, schema_type=s.User)

    async def get_one(self, user_id: UUID) -> s.User:
        """Get a single user by ID."""
        stmt = (
            sql.select(
                "id",
                "email",
                "name",
                "is_superuser",
                "is_active",
                "is_verified",
                "created_at",
                "updated_at",
            )
            .from_("user_account")
            .where_eq("id", user_id)
        )
        # Using the get_or_404 helper for better error handling
        return await self.get_or_404(stmt, schema_type=s.User, error_message=f"User {user_id} not found")

    async def get_by_email(self, email: str) -> s.User | None:
        """Get a user by email address."""
        stmt = (
            sql.select("*")
            .from_("user_account")
            .where_eq("email", email)
        )
        # Built-in schema conversion!
        return await self.select_one_or_none(stmt, schema_type=s.User)

    async def list(self, *filters: StatementFilter) -> OffsetPagination[s.User]:
        """List users with pagination and filtering."""
        stmt = (
            sql.select("*")
            .from_("user_account")
            .order_by(sql.column("created_at").desc())
        )
        
        # Use the paginate helper method from base class
        return await self.paginate(stmt, *filters, schema_type=s.User)

    async def authenticate(self, email: str, password: str) -> s.User | None:
        """Authenticate a user by email and password."""
        # First get the user with password hash
        stmt = (
            sql.select("*")
            .from_("user_account")
            .where_eq("email", email)
        )
        user = await self.select_one_or_none(stmt, schema_type=s.User)
        
        if not user:
            return None
            
        # Here you would verify the password hash
        # For now, we'll just return the user if found
        # In production, use proper password verification
        # Example: if not verify_password(password, user.password_hash):
        #             return None
        
        return user

    async def exists_by_email(self, email: str) -> bool:
        """Check if a user exists by email."""
        # Use the exists helper method
        stmt = (
            sql.select("1")
            .from_("user_account")
            .where_eq("email", email)
        )
        return await self.exists(stmt)

    async def update_last_login(self, user_id: UUID) -> None:
        """Update the last login timestamp for a user."""
        stmt = (
            sql.update("user_account")
            .set(last_login=sql.raw("NOW()"))  # Use sql.raw() for SQL functions
            .where_eq("id", user_id)
        )
        # For non-SELECT queries, we can use execute directly
        await self.execute(stmt)
    
    async def search_by_name(self, query: str, limit: int = 10) -> list[s.User]:
        """Search users by name (case-insensitive).
        
        Demonstrates using where_ilike for pattern matching.
        """
        stmt = (
            sql.select("*")
            .from_("user_account")
            .where_ilike("name", f"%{query}%")  # Case-insensitive LIKE
            .order_by(sql.column("name").asc())
            .limit(limit)
        )
        return await self.select(stmt, schema_type=s.User)
    
    async def get_active_users(self, days: int = 30) -> list[s.User]:
        """Get users who have been active in the last N days.
        
        Demonstrates using multiple WHERE conditions.
        """
        stmt = (
            sql.select("*")
            .from_("user_account")
            .where_eq("is_active", True)
            .where_is_not_null("last_login")
            .where_gte("last_login", sql.raw(f"NOW() - INTERVAL '{days} days'"))
            .order_by(sql.column("last_login").desc())
        )
        return await self.select(stmt, schema_type=s.User)