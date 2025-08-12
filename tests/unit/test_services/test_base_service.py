"""Unit tests for base service functionality."""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import uuid4

import pytest

from sqlstack import schemas as s
from sqlstack.services._base import SQLSpecService

if TYPE_CHECKING:
    from sqlspec.adapters.asyncpg import AsyncpgDriver

pytestmark = pytest.mark.anyio


class TestSQLSpecService:
    """Test base SQLSpecService functionality."""

    async def test_get_or_404_success(self, driver: AsyncpgDriver, test_user: s.User) -> None:
        """Test get_or_404 with existing record."""
        service = SQLSpecService(driver)

        from sqlspec import sql
        result = await service.get_or_404(
            sql.select("id", "email", "name", "is_active", "is_verified", "is_superuser")
            .from_("user_account")
            .where_eq("id", test_user.id),
            schema_type=s.User,
        )

        assert result.id == test_user.id
        assert result.email == test_user.email

    async def test_get_or_404_not_found(self, driver: AsyncpgDriver) -> None:
        """Test get_or_404 with non-existent record."""
        service = SQLSpecService(driver)
        non_existent_id = uuid4()

        from sqlspec import sql
        with pytest.raises(ValueError, match="Record not found"):
            await service.get_or_404(
                sql.select("id", "email", "name", "is_active", "is_verified", "is_superuser")
                .from_("user_account")
                .where_eq("id", non_existent_id),
                schema_type=s.User,
            )

    async def test_get_or_404_custom_error_message(self, driver: AsyncpgDriver) -> None:
        """Test get_or_404 with custom error message."""
        service = SQLSpecService(driver)
        non_existent_id = uuid4()

        from sqlspec import sql
        with pytest.raises(ValueError, match="Custom error message"):
            await service.get_or_404(
                sql.select("id", "email", "name", "is_active", "is_verified", "is_superuser")
                .from_("user_account")
                .where_eq("id", non_existent_id),
                schema_type=s.User,
                error_message="Custom error message",
            )

    async def test_exists_true(self, driver: AsyncpgDriver, test_user: s.User) -> None:
        """Test exists method with existing record."""
        service = SQLSpecService(driver)

        from sqlspec import sql
        exists = await service.exists(
            sql.select("1").from_("user_account").where_eq("id", test_user.id)
        )

        assert exists is True

    async def test_exists_false(self, driver: AsyncpgDriver) -> None:
        """Test exists method with non-existent record."""
        service = SQLSpecService(driver)
        non_existent_id = uuid4()

        from sqlspec import sql
        exists = await service.exists(
            sql.select("1").from_("user_account").where_eq("id", non_existent_id)
        )

        assert exists is False

    async def test_find_filter(self, driver: AsyncpgDriver) -> None:
        """Test find_filter static method."""
        from sqlspec.core.filters import LimitOffsetFilter, SearchFilter

        limit_filter = LimitOffsetFilter(limit=10, offset=0)
        search_filter = SearchFilter(field_name="name", value="test")
        filters = [limit_filter, search_filter]

        # Test finding existing filter
        found_limit = SQLSpecService.find_filter(LimitOffsetFilter, filters)
        assert found_limit is limit_filter

        found_search = SQLSpecService.find_filter(SearchFilter, filters)
        assert found_search is search_filter

        # Test finding non-existent filter type
        from sqlspec.core.filters import BeforeAfterFilter
        not_found = SQLSpecService.find_filter(BeforeAfterFilter, filters)
        assert not_found is None
