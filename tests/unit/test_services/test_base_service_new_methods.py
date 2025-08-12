"""Unit tests for new base service methods."""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlglot import exp

from sqlstack.services._base import SQLSpecService

if TYPE_CHECKING:
    from sqlspec.adapters.asyncpg import AsyncpgDriver

pytestmark = pytest.mark.anyio


async def test_begin_transaction_success(driver: "AsyncpgDriver") -> None:
    """Test successful transaction begin."""
    service = SQLSpecService(driver)
    driver.begin = AsyncMock()
    
    await service.begin()
    
    driver.begin.assert_called_once()


async def test_commit_transaction(driver: "AsyncpgDriver") -> None:
    """Test transaction commit."""
    service = SQLSpecService(driver)
    driver.commit = AsyncMock()
    
    await service.commit()
    
    driver.commit.assert_called_once()


async def test_rollback_transaction(driver: "AsyncpgDriver") -> None:
    """Test transaction rollback."""
    service = SQLSpecService(driver)
    driver.rollback = AsyncMock()
    
    await service.rollback()
    
    driver.rollback.assert_called_once()


async def test_begin_transaction_context_manager_success(driver: "AsyncpgDriver") -> None:
    """Test successful transaction context manager."""
    service = SQLSpecService(driver)
    driver.begin = AsyncMock()
    driver.commit = AsyncMock()
    driver.rollback = AsyncMock()
    
    async with service.begin_transaction():
        # Simulate some work
        pass
    
    driver.begin.assert_called_once()
    driver.commit.assert_called_once()
    driver.rollback.assert_not_called()


async def test_begin_transaction_context_manager_rollback(driver: "AsyncpgDriver") -> None:
    """Test transaction context manager with exception rollback."""
    service = SQLSpecService(driver)
    driver.begin = AsyncMock()
    driver.commit = AsyncMock()
    driver.rollback = AsyncMock()
    
    with pytest.raises(ValueError, match="Test exception"):
        async with service.begin_transaction():
            raise ValueError("Test exception")
    
    driver.begin.assert_called_once()
    driver.commit.assert_not_called()
    driver.rollback.assert_called_once()


async def test_nested_transaction_context_usage(driver: "AsyncpgDriver") -> None:
    """Test using transaction context for actual database operations."""
    service = SQLSpecService(driver)
    driver.begin = AsyncMock()
    driver.commit = AsyncMock() 
    driver.rollback = AsyncMock()
    
    # Mock some database operations
    driver.execute = AsyncMock()
    
    async with service.begin_transaction():
        await driver.execute("INSERT INTO test_table (name) VALUES ($1)", "test")
        await driver.execute("UPDATE test_table SET name = $1 WHERE id = $2", "updated", 1)
    
    # Verify transaction methods were called
    driver.begin.assert_called_once()
    driver.commit.assert_called_once()
    driver.rollback.assert_not_called()
    
    # Verify operations were called
    assert driver.execute.call_count == 2


class TestWithOnlySelectMethod:
    """Test the with_only_select method for query transformation."""

    def test_with_only_select_querybuilder_simple(self, driver: AsyncpgDriver) -> None:
        """Test with_only_select with simple QueryBuilder."""
        from sqlspec import sql
        
        service = SQLSpecService(driver)
        
        # Create a simple SELECT query
        query = sql.select("id", "name", "email").from_("users").where_eq("active", True).order_by("name").limit(10)
        
        # Transform to COUNT query
        count_sql = service.with_only_select(query)
        
        # Should be a COUNT(*) query without ORDER BY, LIMIT
        assert "COUNT(*)" in count_sql
        assert "users" in count_sql
        assert "ORDER BY" not in count_sql
        assert "LIMIT" not in count_sql
        # WHERE clause should be preserved
        assert "active" in count_sql

    def test_with_only_select_querybuilder_with_group_by(self, driver: AsyncpgDriver) -> None:
        """Test with_only_select with GROUP BY query."""
        from sqlspec import sql
        
        service = SQLSpecService(driver)
        
        # Create a grouped SELECT query
        query = sql.select("category", "COUNT(*)").from_("products").group_by("category").order_by("category")
        
        # Transform to COUNT query
        count_sql = service.with_only_select(query)
        
        # Should wrap in subquery for GROUP BY
        assert "COUNT(*)" in count_sql
        assert "products" in count_sql
        assert "GROUP BY" in count_sql
        # Should not have original ORDER BY in final query
        count_sql_upper = count_sql.upper()
        # The original ORDER BY should not be in the outer query
        outer_parts = count_sql.split("GROUP BY")[0] if "GROUP BY" in count_sql else count_sql
        assert "ORDER BY" not in outer_parts.upper()

    def test_with_only_select_querybuilder_with_where_and_having(self, driver: AsyncpgDriver) -> None:
        """Test with_only_select preserves WHERE and HAVING clauses."""
        from sqlspec import sql
        
        service = SQLSpecService(driver)
        
        # Create a complex SELECT query
        query = (sql.select("department", "AVG(salary)")
                .from_("employees")
                .where_eq("active", True)
                .group_by("department")
                .having("AVG(salary) > 50000")
                .order_by("department"))
        
        # Transform to COUNT query
        count_sql = service.with_only_select(query)
        
        # Should preserve WHERE and HAVING
        assert "COUNT(*)" in count_sql
        assert "employees" in count_sql
        assert "active" in count_sql  # WHERE preserved
        assert "50000" in count_sql   # HAVING preserved

    def test_with_only_select_sql_object_with_expression(self, driver: AsyncpgDriver) -> None:
        """Test with_only_select with SQL object that has expression."""
        service = SQLSpecService(driver)
        
        # Create a mock SQL object with expression
        mock_sql = MagicMock()
        mock_expression = exp.select().select("id", "name").from_("users").where("active = 1")
        mock_sql.expression = mock_expression
        
        # Transform to COUNT query
        count_sql = service.with_only_select(mock_sql)
        
        # Should be a COUNT(*) query
        assert "COUNT(*)" in count_sql
        assert "users" in count_sql

    def test_with_only_select_string_input(self, driver: AsyncpgDriver) -> None:
        """Test with_only_select with string SQL input."""
        service = SQLSpecService(driver)
        
        # Test with string SQL
        sql_string = "SELECT id, name FROM users WHERE active = true ORDER BY name LIMIT 10"
        
        count_sql = service.with_only_select(sql_string)
        
        # Should be a COUNT(*) query
        assert "COUNT(*)" in count_sql
        assert "users" in count_sql
        assert "ORDER BY" not in count_sql
        assert "LIMIT" not in count_sql

    def test_with_only_select_non_select_statement(self, driver: AsyncpgDriver) -> None:
        """Test with_only_select raises error for non-SELECT statements."""
        service = SQLSpecService(driver)
        
        # Test with INSERT statement
        insert_sql = "INSERT INTO users (name) VALUES ('test')"
        
        with pytest.raises(TypeError, match="with_only_select can only be used with SELECT statements"):
            service.with_only_select(insert_sql)

    def test_with_only_select_invalid_sql(self, driver: AsyncpgDriver) -> None:
        """Test with_only_select with invalid SQL."""
        service = SQLSpecService(driver)
        
        # Test with invalid SQL
        invalid_sql = "INVALID SQL STATEMENT"
        
        with pytest.raises(ValueError, match="Failed to parse SQL statement"):
            service.with_only_select(invalid_sql)

    @patch("sqlglot.parse_one")
    def test_with_only_select_parsing_error(self, mock_parse, driver: AsyncpgDriver) -> None:
        """Test with_only_select handles parsing errors."""
        service = SQLSpecService(driver)
        mock_parse.side_effect = Exception("Parse error")
        
        with pytest.raises(ValueError, match="Failed to parse SQL statement"):
            service.with_only_select("SELECT * FROM users")

    def test_with_only_select_preserves_complex_where_conditions(self, driver: AsyncpgDriver) -> None:
        """Test that complex WHERE conditions are preserved."""
        from sqlspec import sql
        
        service = SQLSpecService(driver)
        
        # Create query with complex WHERE
        query = (sql.select("*")
                .from_("users")
                .where("active = true AND (role = 'admin' OR role = 'moderator')")
                .order_by("created_at DESC"))
        
        count_sql = service.with_only_select(query)
        
        # Complex WHERE should be preserved
        assert "COUNT(*)" in count_sql
        assert "active" in count_sql
        assert "admin" in count_sql
        assert "moderator" in count_sql
        # ORDER BY should be removed
        assert "ORDER BY" not in count_sql.upper()

    def test_with_only_select_multiple_table_query(self, driver: AsyncpgDriver) -> None:
        """Test with_only_select works with JOINs."""
        service = SQLSpecService(driver)
        
        # Test with JOIN query
        join_sql = """
        SELECT u.id, u.name, p.title 
        FROM users u 
        JOIN profiles p ON u.id = p.user_id 
        WHERE u.active = true 
        ORDER BY u.name
        """
        
        count_sql = service.with_only_select(join_sql)
        
        # Should preserve JOIN and WHERE
        assert "COUNT(*)" in count_sql
        assert "JOIN" in count_sql.upper()
        assert "users" in count_sql
        assert "profiles" in count_sql
        assert "active" in count_sql