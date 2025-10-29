"""Base service module for sqlspec."""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import TYPE_CHECKING, Any, TypeVar

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
from sqlspec.driver import AsyncDriverAdapterBase
from sqlspec.typing import SchemaT, StatementParameters

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from sqlspec import QueryBuilder, Statement, StatementConfig

__all__ = (
    "AnyCollectionFilter",
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
    "SQLSpecService",
    "SearchFilter",
    "StatementFilter",
    "apply_filter",
)

T = TypeVar("T")
AsyncDriverT = TypeVar("AsyncDriverT", bound=AsyncDriverAdapterBase)


class SQLSpecService:
    """Base service class for SQLSpec operations."""

    def __init__(self, driver: AsyncDriverAdapterBase) -> None:
        """Initialize the service."""
        self.driver = driver

    async def paginate(
        self,
        statement: Statement | QueryBuilder,
        /,
        *parameters: StatementParameters | StatementFilter,
        schema_type: type[SchemaT],
        statement_config: StatementConfig | None = None,
        **kwargs: Any,
    ) -> OffsetPagination[SchemaT]:
        """Paginate the data."""
        results, total = await self.driver.select_with_total(
            statement,
            *parameters,
            schema_type=schema_type,
            statement_config=statement_config,
            **kwargs,
        )
        limit_offset = self.driver.find_filter(LimitOffsetFilter, parameters)
        offset = limit_offset.offset if limit_offset else 0
        limit = limit_offset.limit if limit_offset else 10
        return OffsetPagination[SchemaT](items=results, limit=limit, offset=offset, total=total)

    async def get_or_404(
        self,
        statement: Statement | QueryBuilder,
        /,
        *parameters: StatementParameters,
        schema_type: type[SchemaT],
        error_message: str | None = None,
        statement_config: StatementConfig | None = None,
        **kwargs: Any,
    ) -> SchemaT:
        """Get a single record or raise 404 error if not found.

        Args:
            statement: The SQL statement to execute
            *parameters: Statement parameters
            schema_type: The schema type for the result
            error_message: Custom error message (optional)
            statement_config: Optional statement configuration
            **kwargs: Additional keyword arguments

        Returns:
            The found record

        Raises:
            ValueError: If no record is found
        """
        result = await self.driver.select_one_or_none(
            statement,
            *parameters,
            schema_type=schema_type,
            statement_config=statement_config,
            **kwargs,
        )
        if result is None:
            raise ValueError(error_message or "Record not found")
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
            statement: The SQL statement to execute
            *parameters: Statement parameters
            statement_config: Optional statement configuration
            **kwargs: Additional keyword arguments

        Returns:
            True if record exists, False otherwise
        """
        result = await self.driver.select_one_or_none(
            statement,
            *parameters,
            statement_config=statement_config,
            **kwargs,
        )
        return result is not None

    async def begin(self) -> None:
        """Begin a database transaction.

        This method starts a new database transaction. You must call either
        commit() or rollback() to complete the transaction, or use the
        begin_transaction() context manager for automatic handling.
        """
        await self.driver.begin()

    async def commit(self) -> None:
        """Commit the current database transaction.

        This method commits all changes made during the current transaction.
        The transaction must have been started with begin().
        """
        await self.driver.commit()

    async def rollback(self) -> None:
        """Rollback the current database transaction.

        This method rolls back all changes made during the current transaction.
        The transaction must have been started with begin().
        """
        await self.driver.rollback()

    @asynccontextmanager
    async def begin_transaction(self) -> AsyncIterator[None]:
        """Context manager for database transactions."""
        await self.begin()
        try:
            yield
        except Exception:
            await self.rollback()
            raise
        else:
            await self.commit()
