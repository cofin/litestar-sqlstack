"""Export system with registry pattern.

This module provides an extensible export system using the strategy pattern
with a decorator-based registry for registering exporters.

Example:
    from sqlstack.lib.export import (
        AbstractExporter,
        ExportFormat,
        ExportRegistry,
        ExportType,
    )

    @ExportRegistry.register(ExportType.REPORT, ExportFormat.CSV)
    class ReportCsvExporter(AbstractExporter[list[dict]]):
        @property
        def export_type(self) -> ExportType:
            return ExportType.REPORT

        @property
        def export_format(self) -> ExportFormat:
            return ExportFormat.CSV

        async def generate(
            self,
            data: list[dict],
            options: dict | None = None,
        ) -> bytes:
            # Generate CSV content
            ...
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Callable
from enum import Enum
from typing import Any, ClassVar, Generic, TypeVar

__all__ = [
    "AbstractExporter",
    "ExportFormat",
    "ExportRegistry",
    "ExportType",
]


class ExportType(Enum):
    """Types of exports available.

    This enum defines the different categories of exports that can be
    generated. Add new types here as needed for your application.
    """

    REPORT = "report"
    DATA = "data"
    SUMMARY = "summary"
    AUDIT = "audit"


class ExportFormat(Enum):
    """Output formats for exports.

    This enum defines the available output formats for generated exports.
    """

    JSON = "json"
    CSV = "csv"
    HTML = "html"
    PDF = "pdf"
    EXCEL = "xlsx"


ExportDataT = TypeVar("ExportDataT")


class AbstractExporter(ABC, Generic[ExportDataT]):
    """Base class for all exporters.

    Exporters are responsible for converting data into a specific output format.
    Each exporter handles a specific combination of ExportType and ExportFormat.

    Subclasses must implement:
    - export_type: The type of export this handles
    - export_format: The output format
    - generate: The actual export generation logic
    """

    @property
    @abstractmethod
    def export_type(self) -> ExportType:
        """Return the type of export this handles."""

    @property
    @abstractmethod
    def export_format(self) -> ExportFormat:
        """Return the output format."""

    @abstractmethod
    async def generate(self, data: ExportDataT, options: dict[str, Any] | None = None) -> bytes:
        """Generate the export output.

        Args:
            data: The data to export
            options: Optional configuration for the export

        Returns:
            The exported content as bytes
        """

    def get_content_type(self) -> str:
        """Return the MIME content type for this export format."""
        content_types = {
            ExportFormat.JSON: "application/json",
            ExportFormat.CSV: "text/csv",
            ExportFormat.HTML: "text/html",
            ExportFormat.PDF: "application/pdf",
            ExportFormat.EXCEL: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        }
        return content_types.get(self.export_format, "application/octet-stream")

    def get_file_extension(self) -> str:
        """Return the file extension for this export format."""
        return self.export_format.value


class ExportRegistry:
    """Registry for exporter classes.

    This registry provides a centralized way to manage exporters using
    a decorator-based registration pattern.

    Example:
        @ExportRegistry.register(ExportType.REPORT, ExportFormat.JSON)
        class ReportJsonExporter(AbstractExporter[ReportData]):
            ...

        # Later, get the exporter
        exporter_class = ExportRegistry.get_exporter(
            ExportType.REPORT,
            ExportFormat.JSON,
        )
        if exporter_class:
            exporter = exporter_class()
            content = await exporter.generate(data)
    """

    _exporters: ClassVar[dict[tuple[ExportType, ExportFormat], type[AbstractExporter[Any]]]] = {}

    @classmethod
    def register(
        cls, export_type: ExportType, export_format: ExportFormat
    ) -> Callable[[type[AbstractExporter[Any]]], type[AbstractExporter[Any]]]:
        """Decorator to register an exporter class.

        Args:
            export_type: The type of export
            export_format: The output format

        Returns:
            Decorator function that registers the exporter class
        """

        def decorator(exporter_class: type[AbstractExporter[Any]]) -> type[AbstractExporter[Any]]:
            cls._exporters[(export_type, export_format)] = exporter_class
            return exporter_class

        return decorator

    @classmethod
    def get_exporter(
        cls, export_type: ExportType, export_format: ExportFormat
    ) -> type[AbstractExporter[Any]] | None:
        """Get an exporter for the given type and format.

        Args:
            export_type: The type of export
            export_format: The output format

        Returns:
            The exporter class if found, None otherwise
        """
        return cls._exporters.get((export_type, export_format))

    @classmethod
    def list_exporters(cls) -> list[tuple[ExportType, ExportFormat]]:
        """List all registered exporter combinations.

        Returns:
            List of (export_type, export_format) tuples
        """
        return list(cls._exporters.keys())

    @classmethod
    def has_exporter(cls, export_type: ExportType, export_format: ExportFormat) -> bool:
        """Check if an exporter is registered for the given type and format.

        Args:
            export_type: The type of export
            export_format: The output format

        Returns:
            True if an exporter is registered, False otherwise
        """
        return (export_type, export_format) in cls._exporters
