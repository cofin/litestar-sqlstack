"""Unit tests for user-related schemas."""

from __future__ import annotations

from uuid import uuid4

from sqlstack import schemas as s


class TestUserSchemas:
    """Test user-related schema validation and serialization."""

    def test_user_create_schema(self) -> None:
        """Test UserCreate schema validation."""
        user_data = s.UserCreate(
            email="test@example.com",
            password="TestPassword123!",
            name="Test User",
            is_active=True,
            is_verified=False,
        )

        assert user_data.email == "test@example.com"
        assert user_data.password == "TestPassword123!"
        assert user_data.name == "Test User"
        assert user_data.is_active is True
        assert user_data.is_verified is False
        assert user_data.is_superuser is False  # Default

    def test_user_create_minimal(self) -> None:
        """Test UserCreate with minimal required fields."""
        user_data = s.UserCreate(
            email="minimal@example.com",
            password="MinimalPassword123!",
        )

        assert user_data.email == "minimal@example.com"
        assert user_data.password == "MinimalPassword123!"
        assert user_data.name is None  # Default
        assert user_data.is_active is True  # Default
        assert user_data.is_verified is False  # Default
        assert user_data.is_superuser is False  # Default

    def test_user_schema(self) -> None:
        """Test User schema structure."""
        user_id = uuid4()
        user = s.User(
            id=user_id,
            email="user@example.com",
            name="User Name",
            is_active=True,
            is_verified=True,
            is_superuser=False,
        )

        assert user.id == user_id
        assert user.email == "user@example.com"
        assert user.name == "User Name"
        assert user.is_active is True
        assert user.is_verified is True
        assert user.is_superuser is False
        assert user.has_password is False  # Default
        assert user.teams == []  # Default
        assert user.roles == []  # Default
        assert user.oauth_accounts == []  # Default
        assert user.avatar_url is None  # Default

    def test_user_update_schema(self) -> None:
        """Test UserUpdate schema with partial updates."""
        # Test updating only name
        update_data = s.UserUpdate(name="New Name")

        # In msgspec, we need to check the actual values
        assert hasattr(update_data, "name")

        # Test updating multiple fields
        update_data2 = s.UserUpdate(
            name="Another Name",
            is_active=False,
            is_verified=True,
        )

        assert hasattr(update_data2, "name")
        assert hasattr(update_data2, "is_active")
        assert hasattr(update_data2, "is_verified")

    def test_account_login_schema(self) -> None:
        """Test AccountLogin schema."""
        login_data = s.AccountLogin(
            username="user@example.com",
            password="LoginPassword123!",
        )

        assert login_data.username == "user@example.com"
        assert login_data.password == "LoginPassword123!"

    def test_account_register_schema(self) -> None:
        """Test AccountRegister schema."""
        register_data = s.AccountRegister(
            email="register@example.com",
            password="RegisterPassword123!",
            name="Register User",
        )

        assert register_data.email == "register@example.com"
        assert register_data.password == "RegisterPassword123!"
        assert register_data.name == "Register User"

    def test_account_register_minimal(self) -> None:
        """Test AccountRegister with minimal fields."""
        register_data = s.AccountRegister(
            email="minimal@example.com",
            password="MinimalPassword123!",
        )

        assert register_data.email == "minimal@example.com"
        assert register_data.password == "MinimalPassword123!"
        assert register_data.name is None  # Default

    def test_password_update_schema(self) -> None:
        """Test PasswordUpdate schema."""
        password_data = s.PasswordUpdate(
            current_password="OldPassword123!",
            new_password="NewPassword123!",
        )

        assert password_data.current_password == "OldPassword123!"
        assert password_data.new_password == "NewPassword123!"

    def test_password_verify_schema(self) -> None:
        """Test PasswordVerify schema."""
        verify_data = s.PasswordVerify(
            current_password="VerifyPassword123!",
        )

        assert verify_data.current_password == "VerifyPassword123!"

    def test_profile_update_schema(self) -> None:
        """Test ProfileUpdate schema."""
        profile_data = s.ProfileUpdate(
            name="New Profile Name",
        )

        assert hasattr(profile_data, "name")

    def test_user_role_schema(self) -> None:
        """Test UserRole nested schema."""
        role_id = uuid4()
        user_role = s.UserRole(
            role_id=role_id,
            role_slug="admin",
            role_name="Administrator",
            assigned_at="2024-01-01T00:00:00Z",
        )

        assert user_role.role_id == role_id
        assert user_role.role_slug == "admin"
        assert user_role.role_name == "Administrator"
        assert user_role.assigned_at == "2024-01-01T00:00:00Z"

    def test_user_team_schema(self) -> None:
        """Test UserTeam nested schema."""
        team_id = uuid4()
        user_team = s.UserTeam(
            team_id=team_id,
            team_name="Test Team",
            is_owner=False,
            role=s.TeamRoles.MEMBER,
        )

        assert user_team.team_id == team_id
        assert user_team.team_name == "Test Team"
        assert user_team.is_owner is False
        assert user_team.role == s.TeamRoles.MEMBER

    def test_oauth_account_schema(self) -> None:
        """Test OauthAccount nested schema."""
        oauth_id = uuid4()
        oauth_account = s.OauthAccount(
            id=oauth_id,
            oauth_name="google",
            access_token="access-token-123",
            account_id="google-account-id",
            account_email="oauth@example.com",
        )

        assert oauth_account.id == oauth_id
        assert oauth_account.oauth_name == "google"
        assert oauth_account.access_token == "access-token-123"
        assert oauth_account.account_id == "google-account-id"
        assert oauth_account.account_email == "oauth@example.com"
        assert oauth_account.expires_at is None  # Default
        assert oauth_account.refresh_token is None  # Default

    def test_user_role_add_schema(self) -> None:
        """Test UserRoleAdd schema."""
        role_add = s.UserRoleAdd(user_name="testuser")
        assert role_add.user_name == "testuser"

    def test_user_role_revoke_schema(self) -> None:
        """Test UserRoleRevoke schema."""
        role_revoke = s.UserRoleRevoke(user_name="testuser")
        assert role_revoke.user_name == "testuser"
