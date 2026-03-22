"""Base service module for SQLSpec.

Provides base service classes for async and sync database operations
with common patterns like pagination, get_or_404, and transactions.
"""

from __future__ import annotations

from contextlib import asynccontextmanager, contextmanager
from typing import TYPE_CHECKING, Any, TypeVar, cast, overload

from sqlspec import AsyncDriverAdapterBase, SyncDriverAdapterBase
from sqlspec.core.filters import (
    AnyCollectionFilter,
    BeforeAfterFilter,
    FilterTypes,
    FilterTypeT,
    InAnyFilter,
    InCollectionFilter,
    LimitOffsetFilter,
    NotAnyCollectionFilter,
    NotInCollectionFilter,
    NotInSearchFilter,
    OffsetPagination,
    OnBeforeAfterFilter,
    OrderByFilter,
    PaginationFilter,
    SearchFilter,
    StatementFilter,
    apply_filter,
)
from sqlspec.typing import SchemaT, StatementParameters

from sqlstack.lib.exceptions import NotFoundError

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Iterator

    from sqlspec import QueryBuilder, Statement, StatementConfig

__all__ = (
    "AnyCollectionFilter",
    "AsyncDriverAdapterBase",
    "BeforeAfterFilter",
    "FilterTypeT",
    "FilterTypes",
    "InAnyFilter",
    "InCollectionFilter",
    "LimitOffsetFilter",
    "NotAnyCollectionFilter",
    "NotInCollectionFilter",
    "NotInSearchFilter",
    "OffsetPagination",
    "OnBeforeAfterFilter",
    "OrderByFilter",
    "PaginationFilter",
    "SQLSpecAsyncService",
    "SQLSpecSyncService",
    "SchemaT",
    "SearchFilter",
    "StatementFilter",
    "StatementParameters",
    "SyncDriverAdapterBase",
    "apply_filter",
    "encode_offset_pagination",
)

T = TypeVar("T")


class SQLSpecAsyncService:
    """Base service class for async SQLSpec operations.

    Provides common patterns for database operations including pagination,
    single record retrieval with 404 handling, existence checks, and
    transaction management.
    """

    def __init__(self, driver: AsyncDriverAdapterBase) -> None:
        """Initialize the service.

        Args:
            driver: The async database driver adapter.
        """
        self.driver = driver

    @overload
    async def paginate(
        self,
        statement: Statement | QueryBuilder,
        /,
        *parameters: StatementParameters,
        schema_type: None = None,
        error_message: str | None = None,
        statement_config: StatementConfig | None = None,
        **kwargs: Any,
    ) -> OffsetPagination[dict[str, Any]]: ...

    @overload
    async def paginate(
        self,
        statement: Statement | QueryBuilder,
        /,
        *parameters: StatementParameters,
        schema_type: type[SchemaT],
        error_message: str | None = None,
        statement_config: StatementConfig | None = None,
        **kwargs: Any,
    ) -> OffsetPagination[SchemaT]: ...

    async def paginate(
        self,
        statement: Statement | QueryBuilder,
        /,
        *parameters: StatementParameters | StatementFilter,
        schema_type: type[SchemaT] | None = None,
        statement_config: StatementConfig | None = None,
        **kwargs: Any,
    ) -> OffsetPagination[SchemaT] | OffsetPagination[dict[str, Any]]:
        """Paginate query results.

        Args:
            statement: The SQL statement or query builder.
            *parameters: Statement parameters and filters.
            schema_type: Optional schema type for result mapping.
            statement_config: Optional statement configuration.
            **kwargs: Additional keyword arguments.

        Returns:
            Paginated results with total count.
        """
        results, total = await self.driver.select_with_total(
            statement, *parameters, schema_type=schema_type, statement_config=statement_config, **kwargs
        )
        limit_offset = self.driver.find_filter(LimitOffsetFilter, parameters)
        offset = limit_offset.offset if limit_offset else 0
        limit = limit_offset.limit if limit_offset else 10
        if schema_type is None:
            return OffsetPagination[dict[str, Any]](
                items=cast("list[dict[str, Any]]", results), limit=limit, offset=offset, total=total
            )
        return OffsetPagination[SchemaT](items=cast("list[SchemaT]", results), limit=limit, offset=offset, total=total)

    @overload
    async def get_or_404(
        self,
        statement: Statement | QueryBuilder,
        /,
        *parameters: StatementParameters,
        schema_type: None = None,
        error_message: str | None = None,
        statement_config: StatementConfig | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]: ...

    @overload
    async def get_or_404(
        self,
        statement: Statement | QueryBuilder,
        /,
        *parameters: StatementParameters,
        schema_type: type[SchemaT],
        error_message: str | None = None,
        statement_config: StatementConfig | None = None,
        **kwargs: Any,
    ) -> SchemaT: ...

    async def get_or_404(
        self,
        statement: Statement | QueryBuilder,
        /,
        *parameters: StatementParameters,
        schema_type: type[SchemaT] | None = None,
        error_message: str | None = None,
        statement_config: StatementConfig | None = None,
        **kwargs: Any,
    ) -> SchemaT | dict[str, Any]:
        """Get a single record or raise NotFoundError if not found.

        Args:
            statement: The SQL statement or query builder.
            *parameters: Statement parameters.
            schema_type: Optional schema type for result mapping.
            error_message: Custom error message for 404.
            statement_config: Optional statement configuration.
            **kwargs: Additional keyword arguments.

        Returns:
            The found record.

        Raises:
            NotFoundError: If no record is found.
        """
        result = await self.driver.select_one_or_none(
            statement, *parameters, schema_type=schema_type, statement_config=statement_config, **kwargs
        )
        if result is None:
            raise NotFoundError(error_message or "Record not found")
        return result

    async def exists(
        self,
        statement: Statement | QueryBuilder,
        /,
        *parameters: StatementParameters,
        statement_config: StatementConfig | None = None,
        **kwargs: Any,
    ) -> bool:
        """Check if a record exists.

        Args:
            statement: The SQL statement or query builder.
            *parameters: Statement parameters.
            statement_config: Optional statement configuration.
            **kwargs: Additional keyword arguments.

        Returns:
            True if record exists, False otherwise.
        """
        result = await self.driver.select_one_or_none(
            statement.limit(1), *parameters, statement_config=statement_config, **kwargs
        )
        return result is not None

    async def begin(self) -> None:
        """Begin a database transaction."""
        await self.driver.begin()

    async def commit(self) -> None:
        """Commit the current database transaction."""
        await self.driver.commit()

    async def rollback(self) -> None:
        """Rollback the current database transaction."""
        await self.driver.rollback()

    @asynccontextmanager
    async def begin_transaction(self) -> AsyncIterator[None]:
        """Context manager for database transactions.

        Automatically commits on success or rolls back on exception.

        Yields:
            None
        """
        await self.begin()
        try:
            yield
        except Exception:
            await self.rollback()
            raise
        else:
            await self.commit()


class SQLSpecSyncService:
    """Base service class for sync SQLSpec operations.

    Provides common patterns for database operations including pagination,
    single record retrieval with 404 handling, existence checks, and
    transaction management.
    """

    def __init__(self, driver: SyncDriverAdapterBase) -> None:
        """Initialize the service.

        Args:
            driver: The sync database driver adapter.
        """
        self.driver = driver

    @overload
    def paginate(
        self,
        statement: Statement | QueryBuilder,
        /,
        *parameters: StatementParameters,
        schema_type: None = None,
        error_message: str | None = None,
        statement_config: StatementConfig | None = None,
        **kwargs: Any,
    ) -> OffsetPagination[dict[str, Any]]: ...

    @overload
    def paginate(
        self,
        statement: Statement | QueryBuilder,
        /,
        *parameters: StatementParameters,
        schema_type: type[SchemaT],
        error_message: str | None = None,
        statement_config: StatementConfig | None = None,
        **kwargs: Any,
    ) -> OffsetPagination[SchemaT]: ...

    def paginate(
        self,
        statement: Statement | QueryBuilder,
        /,
        *parameters: StatementParameters | StatementFilter,
        schema_type: type[SchemaT] | None = None,
        statement_config: StatementConfig | None = None,
        **kwargs: Any,
    ) -> OffsetPagination[SchemaT] | OffsetPagination[dict[str, Any]]:
        """Paginate query results.

        Args:
            statement: The SQL statement or query builder.
            *parameters: Statement parameters and filters.
            schema_type: Optional schema type for result mapping.
            statement_config: Optional statement configuration.
            **kwargs: Additional keyword arguments.

        Returns:
            Paginated results with total count.
        """
        results, total = self.driver.select_with_total(
            statement, *parameters, schema_type=schema_type, statement_config=statement_config, **kwargs
        )
        limit_offset = self.driver.find_filter(LimitOffsetFilter, parameters)
        offset = limit_offset.offset if limit_offset else 0
        limit = limit_offset.limit if limit_offset else 10
        if schema_type is None:
            return OffsetPagination[dict[str, Any]](
                items=cast("list[dict[str, Any]]", results), limit=limit, offset=offset, total=total
            )
        return OffsetPagination[SchemaT](items=cast("list[SchemaT]", results), limit=limit, offset=offset, total=total)

    @overload
    def get_or_404(
        self,
        statement: Statement | QueryBuilder,
        /,
        *parameters: StatementParameters,
        schema_type: None = None,
        error_message: str | None = None,
        statement_config: StatementConfig | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]: ...

    @overload
    def get_or_404(
        self,
        statement: Statement | QueryBuilder,
        /,
        *parameters: StatementParameters,
        schema_type: type[SchemaT],
        error_message: str | None = None,
        statement_config: StatementConfig | None = None,
        **kwargs: Any,
    ) -> SchemaT: ...

    def get_or_404(
        self,
        statement: Statement | QueryBuilder,
        /,
        *parameters: StatementParameters,
        schema_type: type[SchemaT] | None = None,
        error_message: str | None = None,
        statement_config: StatementConfig | None = None,
        **kwargs: Any,
    ) -> SchemaT | dict[str, Any]:
        """Get a single record or raise NotFoundError if not found.

        Args:
            statement: The SQL statement or query builder.
            *parameters: Statement parameters.
            schema_type: Optional schema type for result mapping.
            error_message: Custom error message for 404.
            statement_config: Optional statement configuration.
            **kwargs: Additional keyword arguments.

        Returns:
            The found record.

        Raises:
            NotFoundError: If no record is found.
        """
        result = self.driver.select_one_or_none(
            statement, *parameters, schema_type=schema_type, statement_config=statement_config, **kwargs
        )
        if result is None:
            raise NotFoundError(error_message or "Record not found")
        return result

    def exists(
        self,
        statement: Statement | QueryBuilder,
        /,
        *parameters: StatementParameters,
        statement_config: StatementConfig | None = None,
        **kwargs: Any,
    ) -> bool:
        """Check if a record exists.

        Args:
            statement: The SQL statement or query builder.
            *parameters: Statement parameters.
            statement_config: Optional statement configuration.
            **kwargs: Additional keyword arguments.

        Returns:
            True if record exists, False otherwise.
        """
        result = self.driver.select_one_or_none(statement.limit(1), *parameters, statement_config=statement_config, **kwargs)
        return result is not None

    def begin(self) -> None:
        """Begin a database transaction."""
        self.driver.begin()

    def commit(self) -> None:
        """Commit the current database transaction."""
        self.driver.commit()

    def rollback(self) -> None:
        """Rollback the current database transaction."""
        self.driver.rollback()

    @contextmanager
    def begin_transaction(self) -> Iterator[None]:
        """Context manager for database transactions.

        Automatically commits on success or rolls back on exception.

        Yields:
            None
        """
        self.begin()
        try:
            yield
        except Exception:
            self.rollback()
            raise
        else:
            self.commit()


def encode_offset_pagination(pagination: OffsetPagination[Any]) -> dict[str, Any]:
    """Helper to encode OffsetPagination for JSON responses."""
    return {
        "items": pagination.items,
        "limit": pagination.limit,
        "offset": pagination.offset,
        "total": pagination.total,
    }
