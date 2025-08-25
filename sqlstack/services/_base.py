"""Base service module for sqlspec."""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import TYPE_CHECKING, Any, TypeVar, cast

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
from sqlspec.typing import ModelDTOT, StatementParameters

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator, Sequence

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
        schema_type: type[ModelDTOT],
        statement_config: StatementConfig | None = None,
        **kwargs: Any,
    ) -> OffsetPagination[ModelDTOT]:
        """Paginate the data."""
        results, total = await self.driver.select_with_total(
            statement,
            *parameters,
            schema_type=schema_type,
            statement_config=statement_config,
            **kwargs,
        )
        limit_offset = self.find_filter(LimitOffsetFilter, parameters)
        offset = limit_offset.offset if limit_offset else 0
        limit = limit_offset.limit if limit_offset else 10
        return OffsetPagination[ModelDTOT](items=results, limit=limit, offset=offset, total=total)

    async def get_or_404(
        self,
        statement: Statement | QueryBuilder,
        /,
        *parameters: StatementParameters,
        schema_type: type[ModelDTOT],
        error_message: str | None = None,
        statement_config: StatementConfig | None = None,
        **kwargs: Any,
    ) -> ModelDTOT:
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

    @staticmethod
    def find_filter(
        filter_type: type[FilterTypeT],
        filters: Sequence[StatementFilter | StatementParameters] | Sequence[StatementFilter],
    ) -> FilterTypeT | None:
        """Get the filter specified by filter type from the filters.

        Args:
            filter_type: The type of filter to find.
            filters: filter types to apply to the query

        Returns:
            The match filter instance or None
        """
        return next(
            (cast("FilterTypeT | None", filter_) for filter_ in filters if isinstance(filter_, filter_type)),
            None,
        )

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
    async def begin_transaction(self) -> AsyncGenerator[None, None]:
        """Async context manager for database transactions.

        Provides a convenient way to execute multiple operations within a transaction.
        Automatically commits on success or rolls back on error.

        Usage:
            # Automatic transaction management (recommended)
            async with service.begin_transaction():
                await service.create(data1)
                await service.update(id, data2)
                # Commits automatically if no exceptions
            # Rolls back automatically if any exceptions occur

            # Manual transaction management (if needed)
            await service.begin()
            try:
                await service.create(data1)
                await service.update(id, data2)
                await service.commit()
            except Exception:
                await service.rollback()
                raise

        Yields:
            None - The context manager handles transaction lifecycle

        Raises:
            Any exceptions from database operations are re-raised after rollback
        """
        try:
            await self.begin()
            yield
            await self.commit()
        except Exception:
            await self.rollback()
            raise
