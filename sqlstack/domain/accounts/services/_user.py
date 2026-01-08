from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from litestar.exceptions import PermissionDeniedException
from sqlspec import sql
from sqlspec.utils.serializers import schema_dump
from sqlspec.utils.type_guards import is_dict_without_field

from sqlstack.config import db_manager
from sqlstack.domain.accounts import schemas as s
from sqlstack.lib.crypt import get_password_hash, verify_password
from sqlstack.lib.service import OffsetPagination, SQLSpecAsyncService, StatementFilter

if TYPE_CHECKING:
    from uuid import UUID

    from httpx_oauth.oauth2 import OAuth2Token



class UserService(SQLSpecAsyncService):
    """Handles database operations for users using SQLSpec's sql builder API."""

    async def create_user(self, data: s.UserCreate | s.AccountRegister) -> s.User:
        """Create a new user account."""
        from uuid import uuid4

        user_data = schema_dump(data, exclude_unset=True)
        user_data.setdefault("id", uuid4())
        user_data.setdefault("is_superuser", False)
        user_data.setdefault("avatar_url", None)
        user_data.setdefault("joined_at", None)  # Will use CURRENT_DATE in SQL if None
        if has_password := user_data.pop("password", None):
            user_data["hashed_password"] = await get_password_hash(has_password)
        user_id = await self.driver.select_value(db_manager.get_sql("create-user"), user_data)
        # Optionally assign default role if it exists
        role_id = await self.driver.select_value_or_none(sql.select("id").from_("role").where_eq("slug", "member"))
        if role_id:
            await self.driver.execute(
                sql.insert("user_account_role")
                .columns("id", "user_id", "role_id", "assigned_at", "created_at", "updated_at")
                .values(
                    sql.raw("gen_random_uuid()"), user_id, role_id, sql.raw("NOW()"), sql.raw("NOW()"), sql.raw("NOW()")
                )
            )
        return await self.driver.select_one(
            db_manager.get_sql("get-user-account-details"), user_id=user_id, schema_type=s.User
        )

    async def update_user(self, user_id: UUID, data: s.UserUpdate | s.ProfileUpdate) -> s.User:
        """Update an existing user account."""
        await self.driver.execute(
            sql.update("user_account").set(**schema_dump(data, exclude_unset=True)).where_eq("id", user_id)
        )
        return await self.driver.select_one(
            db_manager.get_sql("get-user-account-details"), user_id=user_id, schema_type=s.User
        )

    async def delete_user(self, item_id: UUID) -> None:
        """Delete a user account."""
        await self.driver.execute(sql.delete("user_account").where_eq("id", item_id))

    async def get_user(self, user_id: UUID) -> s.User:
        """Get a single user by ID."""
        return await self.get_or_404(
            db_manager.get_sql("get-user-account-details"),
            user_id=user_id,
            schema_type=s.User,
            error_message=f"User {user_id} not found",
        )

    async def list_with_count(self, *filters: StatementFilter) -> OffsetPagination[s.User]:
        """List users with pagination and filtering."""
        return await self.paginate(db_manager.get_sql("list-users"), *filters, schema_type=s.User)

    async def authenticate(self, email: str, password: str) -> s.User:
        """Authenticate a user by email and password.

        Args:
            email: User's email address
            password: Plain text password to verify

        Raises:
            PermissionDeniedException: If authentication fails

        Returns:
            User object if authentication succeeds
        """
        active_auth = await self.driver.select_one_or_none(
            sql.select("id", "email", "hashed_password", "is_active").from_("user_account").where_eq("email", email)
        )
        if (
            not active_auth
            or active_auth["hashed_password"] is None
            or (not await verify_password(password, active_auth["hashed_password"]))
        ):
            msg = "User not found or password invalid"
            raise PermissionDeniedException(detail=msg)
        if not active_auth["is_active"]:
            msg = "User account is inactive"
            raise PermissionDeniedException(detail=msg)
        await self.update_last_login(active_auth["id"])
        return await self.driver.select_one(
            db_manager.get_sql("get-user-account-details"), user_id=active_auth["id"], schema_type=s.User
        )

    async def update_last_login(self, user_id: UUID) -> None:
        """Update the last login timestamp for a user."""
        await self.driver.execute(sql.update("user_account").set(last_login="NOW()").where_eq("id", user_id))

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
        active_auth = await self.driver.select_one(
            sql.select("id", "email", "hashed_password", "is_active").from_("user_account").where_eq("id", user_id)
        )
        if is_dict_without_field(active_auth, "is_active") or not active_auth["is_active"]:
            msg = "User account is inactive"
            raise ValueError(msg)
        if not await verify_password(current_password, active_auth["hashed_password"]):
            msg = "Current password is incorrect"
            raise ValueError(msg)
        await self.set_password(active_auth["id"], new_password)
        return await self.driver.select_one(
            db_manager.get_sql("get-user-account-details"), user_id=active_auth["id"], schema_type=s.User
        )

    async def set_password(self, user_id: UUID, new_password: str) -> None:
        """Reset a user's password using a valid reset token.

        This method should be called after token validation.

        Args:
            user_id: ID of the user
            new_password: New password to set
        """
        new_password_hash = await get_password_hash(new_password)
        await self.driver.execute(
            sql.update("user_account")
            .set(password_hash=new_password_hash, is_verified=True, updated_at=sql.raw("NOW()"))
            .where_eq("id", user_id)
        )

    @staticmethod
    async def has_role_id(db_obj: s.User, role_id: UUID) -> bool:
        """Return true if user has specified role ID"""
        return any(assigned_role.role_id for assigned_role in db_obj.roles if assigned_role.role_id == role_id)

    @staticmethod
    async def has_role(db_obj: s.User, role_name: str) -> bool:
        """Return true if user has specified role ID"""
        return any(assigned_role.role_id for assigned_role in db_obj.roles if assigned_role.role_name == role_name)

    @staticmethod
    def is_superuser(user: s.User) -> bool:
        return bool(
            any(assigned_role.role_name for assigned_role in user.roles if assigned_role.role_name == "superuser")
        )

    async def deactivate_user(self, user_id: UUID) -> None:
        """Deactivate a user account."""
        await self.driver.execute(
            sql.update("user_account").set(is_active=False, updated_at=sql.raw("NOW()")).where_eq("id", user_id)
        )

    async def activate_user(self, user_id: UUID) -> None:
        """Activate a user account."""
        await self.driver.execute(
            sql.update("user_account").set(is_active=True, updated_at=sql.raw("NOW()")).where_eq("id", user_id)
        )

    async def verify_user(self, user_id: UUID) -> None:
        """Mark a user's email as verified."""
        await self.driver.execute(
            sql.update("user_account").set(is_verified=True, updated_at=sql.raw("NOW()")).where_eq("id", user_id)
        )

    async def authenticate_or_create_oauth_user(
        self,
        provider: str,
        oauth_data: dict[str, Any],
        token_data: OAuth2Token,
    ) -> tuple[s.User, bool]:
        """Authenticate or create a user from OAuth data.

        Args:
            provider: OAuth provider name.
            oauth_data: User data from the provider.
            token_data: OAuth token data.

        Returns:
            Tuple of (User, is_new).
        """
        from sqlstack.domain.accounts.services.user_oauth_account import UserOAuthAccountService

        oauth_service = UserOAuthAccountService(self.driver)
        account_id = oauth_data.get("id", oauth_data.get("sub", ""))
        email = oauth_data.get("email")

        # Check if OAuth account exists
        existing_oauth = await oauth_service.get_by_provider_account_id(provider, account_id)
        if existing_oauth:
            await oauth_service.link_or_update_oauth(
                user_id=existing_oauth.user_id,
                provider=provider,
                account_id=account_id,
                account_email=email,
                access_token=token_data["access_token"],
                refresh_token=token_data.get("refresh_token"),
                expires_at=token_data.get("expires_at"),
                scopes=token_data.get("scope"),
                provider_user_data=oauth_data,
                last_login_at=datetime.now(UTC),
            )
            return await self.get_user(existing_oauth.user_id), False

        # Check if user with email exists
        if email:
            existing_user = await self.driver.select_one_or_none(
                db_manager.get_sql("get-user-account-details"), email=email, schema_type=s.User
            )
            if existing_user:
                await oauth_service.link_or_update_oauth(
                    user_id=existing_user.id,
                    provider=provider,
                    account_id=account_id,
                    account_email=email,
                    access_token=token_data["access_token"],
                    refresh_token=token_data.get("refresh_token"),
                    expires_at=token_data.get("expires_at"),
                    scopes=token_data.get("scope"),
                    provider_user_data=oauth_data,
                    last_login_at=datetime.now(UTC),
                )
                return existing_user, False

        # Create new user
        from uuid import uuid4
        user_id = uuid4()
        user_create = s.UserCreate(
            email=email or f"{user_id}@example.com", # Fallback if no email
            password=str(uuid4()), # Random password
            name=oauth_data.get("name"),
            is_active=True,
            is_verified=True, # Verified since it's OAuth
            is_superuser=False,
        )
        
        # We need to adapt create_user to accept UserCreate with random password hash maybe?
        # UserService.create_user handles hashing.
        
        # Create user
        user = await self.create_user(user_create)
        
        # Link OAuth
        await oauth_service.link_or_update_oauth(
            user_id=user.id,
            provider=provider,
            account_id=account_id,
            account_email=email,
            access_token=token_data["access_token"],
            refresh_token=token_data.get("refresh_token"),
            expires_at=token_data.get("expires_at"),
            scopes=token_data.get("scope"),
            provider_user_data=oauth_data,
            last_login_at=datetime.now(UTC),
        )
        
        return user, True

