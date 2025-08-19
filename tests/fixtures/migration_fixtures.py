"""Migration-based test fixtures using SQLSpec CLI commands."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator
    from pytest_databases.docker.postgres import PostgresService
    from sqlspec.adapters.asyncpg import AsyncpgConnection
    from sqlspec.extensions.litestar.plugin import SQLSpec

pytestmark = pytest.mark.anyio


@pytest.fixture(name="migrated_db_connection")
async def fx_migrated_db_connection(postgres_service: PostgresService) -> AsyncGenerator[AsyncpgConnection, None]:
    """Database connection with migrations applied using SQLSpec migration system."""
    from sqlspec.adapters.asyncpg import AsyncpgConfig
    from sqlspec.config import DatabaseConfig
    from sqlspec.extensions.litestar import SQLSpec
    from sqlspec.migrations.commands import AsyncMigrationCommands
    
    # Create database configuration
    database_url = f"postgresql+asyncpg://{postgres_service.user}:{postgres_service.password}@{postgres_service.host}:{postgres_service.port}/{postgres_service.database}"
    
    config = AsyncpgConfig(
        database_url=database_url,
        migration_config={
            "script_location": str(Path(__file__).parent.parent.parent / "sqlstack" / "db" / "migrations"),
            "version_table_name": "sqlspec_migrations_test",
        },
    )
    
    # Create SQLSpec instance for migrations
    sqlspec = SQLSpec(config=[DatabaseConfig(config=config)])
    migration_commands = AsyncMigrationCommands(config)
    
    # Get connection from driver
    driver = sqlspec.get_driver()
    async with driver.get_connection() as conn:
        try:
            # Run migrations to set up database schema
            migration_path = Path(__file__).parent.parent.parent / "sqlstack" / "db" / "migrations"
            if migration_path.exists():
                # Initialize migration system
                await migration_commands.init(str(migration_path))
                # Run upgrade to head
                await migration_commands.upgrade("head")
            
            yield conn
            
        finally:
            # Clean up using migrations
            try:
                await migration_commands.downgrade("base")
            except Exception:
                # Ignore cleanup errors in tests
                pass


@pytest.fixture(name="migrated_db_manager")
async def fx_migrated_db_manager(migrated_db_connection: AsyncpgConnection) -> SQLSpec:
    """Provide a fully configured SQLSpec instance with migrations applied and SQL queries loaded."""
    from sqlspec.adapters.asyncpg import AsyncpgConfig
    from sqlspec.config import DatabaseConfig
    from sqlspec.extensions.litestar import SQLSpec
    from sqlspec.loaders import SQLFileLoader
    
    # Create SQLSpec instance matching the migrated connection
    database_url = f"postgresql+asyncpg://{migrated_db_connection._connection.get_dsn()}"  # type: ignore[attr-defined]
    
    config = AsyncpgConfig(database_url=database_url)
    sqlspec = SQLSpec(config=[DatabaseConfig(config=config)])
    
    # Load SQL query files using a direct loader approach
    sql_path = Path(__file__).parent.parent.parent / "sqlstack" / "db" / "sql"
    if sql_path.exists():
        try:
            sql_loader = SQLFileLoader()
            for sql_file in sql_path.glob("*.sql"):
                sql_loader.load_queries_from_file(sql_file)
            
            # Store queries in the SQLSpec instance
            sqlspec._sql_queries = sql_loader.queries  # type: ignore[attr-defined]
            
            # Also provide get_sql method for compatibility
            sqlspec.get_sql = lambda name: sqlspec._sql_queries.get(name, f"-- Query '{name}' not found")  # type: ignore[attr-defined,method-assign]
            
        except Exception as e:
            print(f"Warning: Could not load SQL files: {e}")
            # Provide empty get_sql method
            sqlspec.get_sql = lambda name: f"-- Query '{name}' not available"  # type: ignore[method-assign]
    
    return sqlspec


async def run_migration_upgrade() -> None:
    """Helper function to run migration upgrade programmatically."""
    from sqlstack.config import db_manager
    from sqlspec.migrations.commands import AsyncMigrationCommands
    
    # Get the database config from db_manager
    config = db_manager.config[0].config  # First config should be the main DB
    migration_commands = AsyncMigrationCommands(config)
    
    migration_path = Path(__file__).parent.parent.parent / "sqlstack" / "db" / "migrations"
    
    # Initialize and run migrations
    await migration_commands.init(str(migration_path))
    await migration_commands.upgrade("head")


async def run_migration_downgrade() -> None:
    """Helper function to run migration downgrade programmatically.""" 
    from sqlstack.config import db_manager
    from sqlspec.migrations.commands import AsyncMigrationCommands
    
    # Get the database config from db_manager
    config = db_manager.config[0].config  # First config should be the main DB
    migration_commands = AsyncMigrationCommands(config)
    
    # Run downgrade
    await migration_commands.downgrade("base")


def test_migration_files_exist() -> None:
    """Test that required migration and SQL files exist."""
    migration_path = Path(__file__).parent.parent.parent / "sqlstack" / "db" / "migrations"
    sql_path = Path(__file__).parent.parent.parent / "sqlstack" / "db" / "sql"
    
    assert migration_path.exists(), f"Migration directory should exist at {migration_path}"
    assert sql_path.exists(), f"SQL queries directory should exist at {sql_path}"
    
    # Check that initial migration exists
    migration_files = list(migration_path.glob("*.sql"))
    assert len(migration_files) >= 1, "Should have at least one migration file"
    
    # Check that SQL query files exist
    sql_files = list(sql_path.glob("*.sql"))
    assert len(sql_files) >= 4, "Should have SQL files for users, roles, tags, teams"


if __name__ == "__main__":
    # Allow testing migration functionality directly
    asyncio.run(test_migration_files_exist())