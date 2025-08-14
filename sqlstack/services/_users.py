from __future__ import annotations

from typing import TYPE_CHECKING, Any

from sqlspec import sql
from sqlspec.utils.type_guards import is_dict_with_field, is_dict_without_field, schema_dump

from sqlstack import schemas as s
from sqlstack.lib.crypt import get_password_hash, verify_password
from sqlstack.services._base import OffsetPagination, SQLSpecService, StatementFilter

if TYPE_CHECKING:
    from uuid import UUID


class UserService(SQLSpecService):
    """Handles database operations for users using SQLSpec's sql builder API."""

    async def create(self, data: s.UserCreate) -> s.User:
        """Create a new user account."""
        # Prepare data for insertion, hashing the password
        user_data = schema_dump(data, exclude_unset=True)
        # Replace plain text password with hash
        password_hash = await get_password_hash(user_data.pop("password"))
        user_data["password_hash"] = password_hash

        user_record = await self.driver.select_one(
            sql.insert("user_account")
            .values(**user_data)
            .returning(
                "id",
                "email",
                "name",
                "is_superuser",
                "is_active",
                "is_verified",
                "password_hash",
                "avatar_url",
                "created_at",
                "updated_at",
                "last_login",
            ),
        )

        # Convert to User schema (without password_hash field)
        return s.User(
            id=user_record["id"],
            email=user_record["email"],
            name=user_record["name"],
            is_superuser=user_record["is_superuser"],
            is_active=user_record["is_active"],
            is_verified=user_record["is_verified"],
            has_password=user_record["password_hash"] is not None,
            avatar_url=user_record["avatar_url"],
        )

    async def update(self, item_id: UUID, data: s.UserUpdate) -> s.User:
        """Update an existing user account."""
        return await self.driver.select_one(
            sql.update("user_account")
            .set(**schema_dump(data, exclude_unset=True))
            .where_eq("id", item_id)
            .returning(
                "id",
                "email",
                "name",
                "is_superuser",
                "is_active",
                "is_verified",
                sql.case_.when("password_hash IS NOT NULL", True).else_(False).end().as_("has_password"),
                "avatar_url",
                "created_at",
                "updated_at",
                "last_login",
            ),
            schema_type=s.User,
        )

    async def delete(self, item_id: UUID) -> s.User:
        """Delete a user account."""
        return await self.driver.select_one(
            sql.delete("user_account")
            .where_eq("id", item_id)
            .returning(
                "id",
                "email",
                "name",
                "is_superuser",
                "is_active",
                "is_verified",
                sql.case_.when("password_hash IS NOT NULL", True).else_(False).end().as_("has_password"),
                "avatar_url",
                "created_at",
                "updated_at",
                "last_login",
            ),
            schema_type=s.User,
        )

    async def get_one(self, user_id: UUID) -> s.User:
        """Get a single user by ID."""
        return await self.get_or_404(
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
            .where_eq("id", user_id),
            schema_type=s.User,
            error_message=f"User {user_id} not found",
        )

    async def get_by_email(self, email: str) -> s.User | None:
        """Get a user by email address."""
        return await self.driver.select_one_or_none(
            sql.select(
                "id",
                "email",
                "name",
                "is_superuser",
                "is_active",
                "is_verified",
                sql.case_.when("password_hash IS NOT NULL", True).else_(False).end().as_("has_password"),
                "avatar_url",
                "created_at",
                "updated_at",
                "last_login",
            )
            .from_("user_account")
            .where_eq("email", email),
            schema_type=s.User,
        )

    async def list_with_count(self, *filters: StatementFilter) -> OffsetPagination[s.User]:
        """List users with pagination and filtering."""
        return await self.paginate(
            sql.select(
                "id",
                "email",
                "name",
                "is_superuser",
                "is_active",
                "is_verified",
                sql.case_.when("password_hash IS NOT NULL", True).else_(False).end().as_("has_password"),
                "avatar_url",
                "created_at",
                "updated_at",
                "last_login",
            )
            .from_("user_account")
            .order_by(sql.column("created_at").desc()),
            *filters,
            schema_type=s.User,
        )

    async def authenticate(self, email: str, password: str) -> s.User | None:
        """Authenticate a user by email and password.

        Args:
            email: User's email address
            password: Plain text password to verify

        Returns:
            User object if authentication succeeds, None otherwise

        Raises:
            ValueError: If user is inactive or account is locked
        """
        user_record = await self.driver.select_one_or_none(
            sql.select(
                "id",
                "email",
                "name",
                "is_superuser",
                "is_active",
                "is_verified",
                "password_hash",
                "avatar_url",
                "created_at",
                "updated_at",
                "last_login",
            )
            .from_("user_account")
            .where_eq("email", email),
        )

        if not user_record:
            return None

        if not user_record["is_active"]:
            msg = "User account is inactive"
            raise ValueError(msg)

        # Check if user has a password (OAuth users may not have one)
        if user_record["password_hash"] is None:
            return None

        # Verify password
        if not await verify_password(password, user_record["password_hash"]):
            return None

        # Create User schema object (without password_hash field)
        user = s.User(
            id=user_record["id"],
            email=user_record["email"],
            name=user_record["name"],
            is_superuser=user_record["is_superuser"],
            is_active=user_record["is_active"],
            is_verified=user_record["is_verified"],
            has_password=user_record["password_hash"] is not None,
            avatar_url=user_record["avatar_url"],
        )

        # Update last login timestamp
        await self.update_last_login(user.id)

        return user

    async def exists_by_email(self, email: str) -> bool:
        """Check if a user exists by email."""
        return await self.exists(sql.select("1").from_("user_account").where_eq("email", email))

    async def update_last_login(self, user_id: UUID) -> None:
        """Update the last login timestamp for a user."""
        await self.driver.execute(sql.update("user_account").set(last_login=sql.raw("NOW()")).where_eq("id", user_id))

    async def search_by_name(self, query: str, limit: int = 10) -> list[s.User]:
        """Search users by name (case-insensitive)."""
        return await self.driver.select(
            sql.select(
                "id",
                "email",
                "name",
                "is_superuser",
                "is_active",
                "is_verified",
                sql.user,
                sql.raw("user u"),
                sql.case_.when("password_hash IS NOT NULL", True).else_(False).end().as_("has_password"),
                "avatar_url",
                "created_at",
                "updated_at",
                "last_login",
            )
            .from_("user_account")
            .where_ilike("name", f"%{query}%")
            .order_by(sql.column("name").asc())
            .limit(limit),
            schema_type=s.User,
        )

    async def get_active_users(self, days: int = 30) -> list[s.User]:
        """Get users who have been active in the last N days."""
        return await self.driver.select(
            sql.select(
                "id",
                "email",
                "name",
                "is_superuser",
                "is_active",
                "is_verified",
                sql.case_.when("password_hash IS NOT NULL", True).else_(False).end(),
                sql.case_.when("password_hash IS NOT NULL", True).else_(False).end().as_("has_password"),
                "avatar_url",
                "created_at",
                "updated_at",
                "last_login",
            )
            .from_("user_account")
            .where_eq("is_active", True)
            .where_is_not_null("last_login")
            .where_gte("last_login", sql.raw(f"NOW() - INTERVAL '{days} days'"))
            .order_by(sql.column("last_login").desc()),
            schema_type=s.User,
        )

    async def update_password(self, user_id: UUID, current_password: str, new_password: str) -> s.User:
        """Update a user's password after verifying the current password.

        Args:
            user_id: ID of the user
            current_password: Current password for verification
            new_password: New password to set

        Returns:
            Updated user object

        Raises:
            ValueError: If current password is incorrect or user is inactive
        """
        # Get user to verify current password
        user = await self.driver.select_one(
            sql.select("id", "email", "password_hash", "is_active", "is_verified")
            .from_("user_account")
            .where_eq("id", user_id),
        )

        if not user:
            msg = "User not found"
            raise ValueError(msg)

        if is_dict_without_field(user, "is_active") or (
            is_dict_with_field(user, "is_active") and not user["is_active"]
        ):
            msg = "User account is inactive"
            raise ValueError(msg)

        # Verify current password
        if not await verify_password(current_password, user["password_hash"]):
            msg = "Current password is incorrect"
            raise ValueError(msg)

        # Hash new password
        new_password_hash = await get_password_hash(new_password)

        # Update password
        user_record = await self.driver.select_one(
            sql.update("user_account")
            .set(password_hash=new_password_hash, updated_at=sql.raw("NOW()"))
            .where_eq("id", user_id)
            .returning(
                "id",
                "email",
                "name",
                "is_superuser",
                "is_active",
                "is_verified",
                "password_hash",
                "avatar_url",
            ),
        )

        # Convert to User schema (without password_hash field)
        return s.User(
            id=user_record["id"],
            email=user_record["email"],
            name=user_record["name"],
            is_superuser=user_record["is_superuser"],
            is_active=user_record["is_active"],
            is_verified=user_record["is_verified"],
            has_password=user_record["password_hash"] is not None,
            avatar_url=user_record["avatar_url"],
        )

    async def reset_password_with_token(self, user_id: UUID, new_password: str) -> s.User:
        """Reset a user's password using a valid reset token.

        This method should be called after token validation.

        Args:
            user_id: ID of the user
            new_password: New password to set

        Returns:
            Updated user object
        """
        password_hash = await get_password_hash(new_password)
        user_record = await self.driver.select_one(
            sql.update("user_account")
            .set(password_hash=password_hash, is_verified=True, updated_at=sql.raw("NOW()"))
            .where_eq("id", user_id)
            .returning(
                "id", "email", "name", "is_superuser", "is_active", "is_verified", "password_hash", "avatar_url"
            ),
        )

        # Convert to User schema (without password_hash field)
        return s.User(
            id=user_record["id"],
            email=user_record["email"],
            name=user_record["name"],
            is_superuser=user_record["is_superuser"],
            is_active=user_record["is_active"],
            is_verified=user_record["is_verified"],
            has_password=user_record["password_hash"] is not None,
            avatar_url=user_record["avatar_url"],
        )

    async def create_user_from_oauth(self, oauth_data: dict[str, Any], provider_name: str) -> s.User:
        """Create a new user from OAuth provider data.

        Args:
            oauth_data: OAuth user data from provider
            provider_name: Name of the OAuth provider

        Returns:
            Created user object
        """
        user_data = {
            "email": oauth_data.get("email"),
            "name": oauth_data.get("name") or oauth_data.get("login"),
            "avatar_url": oauth_data.get("avatar_url"),
            "is_active": True,
            "is_verified": True,  # OAuth emails are considered verified
            "password_hash": None,  # OAuth users don't have passwords
        }

        # Insert directly since OAuth users don't have passwords and can't use UserCreate schema
        return await self.driver.select_one(
            sql.insert("user_account")
            .values(**user_data)
            .returning(
                "id",
                "email",
                "name",
                "is_superuser",
                "is_active",
                "is_verified",
                sql.case_.when("password_hash IS NOT NULL", True).else_(False).end().as_("has_password"),
                "avatar_url",
                "created_at",
                "updated_at",
                "last_login",
            ),
            schema_type=s.User,
        )

    async def authenticate_or_create_oauth_user(
        self, oauth_data: dict[str, Any], provider_name: str, account_id: str
    ) -> tuple[s.User, bool]:
        """Authenticate or create a user from OAuth provider data.

        Args:
            oauth_data: OAuth user data from provider
            provider_name: Name of the OAuth provider
            account_id: OAuth account ID from provider

        Raises:
            ValueError: If the OAuth provider did not provide an email address

        Returns:
            Tuple of (user, was_created)
        """
        email = oauth_data.get("email")
        if not email:
            msg = "OAuth provider did not provide email address"
            raise ValueError(msg)

        # Try to find existing user by email
        user = await self.get_by_email(email)

        if user:
            # Update last login and return existing user
            await self.update_last_login(user.id)
            return user, False
        # Create new user from OAuth data
        user = await self.create_user_from_oauth(oauth_data, provider_name)
        return user, True

    async def has_role(self, user_id: UUID, role_name: str) -> bool:
        """Check if a user has a specific role by name.

        Args:
            user_id: ID of the user
            role_name: Name of the role to check

        Returns:
            True if user has the role, False otherwise
        """
        return await self.exists(
            sql.select("1")
            .from_("user_role ur")
            .join("role r", "ur.role_id = r.id")
            .where_eq("ur.user_id", user_id)
            .where_eq("r.name", role_name)
        )

    async def has_role_id(self, user_id: UUID, role_id: UUID) -> bool:
        """Check if a user has a specific role by ID.

        Args:
            user_id: ID of the user
            role_id: ID of the role to check

        Returns:
            True if user has the role, False otherwise
        """
        return await self.exists(
            sql.select("1").from_("user_role").where_eq("user_id", user_id).where_eq("role_id", role_id)
        )

    async def is_superuser(self, user_id: UUID) -> bool:
        """Check if a user is a superuser.

        Args:
            user_id: ID of the user

        Returns:
            True if user is a superuser, False otherwise
        """
        result = await self.driver.select_one_or_none(
            sql.select("is_superuser").from_("user_account").where_eq("id", user_id),
        )
        return result["is_superuser"] if result else False

    async def activate_user(self, user_id: UUID) -> s.User:
        """Activate a user account."""
        return await self.driver.select_one(
            sql.update("user_account")
            .set(is_active=True, updated_at=sql.raw("NOW()"))
            .where_eq("id", user_id)
            .returning(
                "id",
                "email",
                "name",
                "is_superuser",
                "is_active",
                "is_verified",
                sql.case_.when("password_hash IS NOT NULL", True).else_(False).end().as_("has_password"),
                "avatar_url",
                "created_at",
                "updated_at",
                "last_login",
            ),
            schema_type=s.User,
        )

    async def deactivate_user(self, user_id: UUID) -> s.User:
        """Deactivate a user account."""
        return await self.driver.select_one(
            sql.update("user_account")
            .set(is_active=False, updated_at=sql.raw("NOW()"))
            .where_eq("id", user_id)
            .returning(
                "id",
                "email",
                "name",
                "is_superuser",
                "is_active",
                "is_verified",
                sql.case_.when("password_hash IS NOT NULL", True).else_(False).end().as_("has_password"),
                "avatar_url",
                "created_at",
                "updated_at",
                "last_login",
            ),
            schema_type=s.User,
        )

    async def verify_user_email(self, user_id: UUID) -> s.User:
        """Mark a user's email as verified."""
        return await self.driver.select_one(
            sql.update("user_account")
            .set(is_verified=True, updated_at=sql.raw("NOW()"))
            .where_eq("id", user_id)
            .returning(
                "id",
                "email",
                "name",
                "is_superuser",
                "is_active",
                sql.is_verified,
                sql.case_.when("password_hash IS NOT NULL", True).else_(False).end().as_("has_password"),
                "avatar_url",
                "created_at",
                "updated_at",
                "last_login",
            ),
            schema_type=s.User,
        )

    async def get_user_statistics(self) -> dict[str, Any]:
        """Get user statistics."""
        return await self.driver.select_one(
            sql.select(
                "COUNT(*) as total_users",
                sql.count(sql.case_.when("is_active = true", 1).end()).as_("active_users"),
                sql.count(sql.case_.when("is_verified = true", 1).end()).as_("verified_users"),
                sql.count(sql.case_.when("is_superuser = true", 1).end()).as_("superusers"),
                sql.count(sql.case_.when("last_login > NOW() - INTERVAL '30 days'", 1).end()).as_("recent_logins"),
            ).from_("user_account"),
        )
