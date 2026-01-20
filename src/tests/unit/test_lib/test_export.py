"""Unit tests for export module."""

from __future__ import annotations

import pytest

from sqlstack.lib.export import (
    AbstractExporter,
    ExportFormat,
    ExportRegistry,
    ExportType,
)


# Test fixtures - concrete exporter implementations for testing
class TestJsonExporter(AbstractExporter[list[dict]]):
    """Test exporter for JSON format."""

    @property
    def export_type(self) -> ExportType:
        return ExportType.REPORT

    @property
    def export_format(self) -> ExportFormat:
        return ExportFormat.JSON

    async def generate(self, data: list[dict], options: dict | None = None) -> bytes:
        import json

        return json.dumps(data).encode()


class TestCsvExporter(AbstractExporter[list[dict]]):
    """Test exporter for CSV format."""

    @property
    def export_type(self) -> ExportType:
        return ExportType.DATA

    @property
    def export_format(self) -> ExportFormat:
        return ExportFormat.CSV

    async def generate(self, data: list[dict], options: dict | None = None) -> bytes:
        return b"csv,data"


class TestExportType:
    """Tests for ExportType enum."""

    def test_export_types_exist(self) -> None:
        """Test that all expected export types exist."""
        assert ExportType.REPORT.value == "report"
        assert ExportType.DATA.value == "data"
        assert ExportType.SUMMARY.value == "summary"
        assert ExportType.AUDIT.value == "audit"

    def test_export_types_are_distinct(self) -> None:
        """Test that all export types have distinct values."""
        values = [t.value for t in ExportType]
        assert len(values) == len(set(values))


class TestExportFormat:
    """Tests for ExportFormat enum."""

    def test_export_formats_exist(self) -> None:
        """Test that all expected export formats exist."""
        assert ExportFormat.JSON.value == "json"
        assert ExportFormat.CSV.value == "csv"
        assert ExportFormat.HTML.value == "html"
        assert ExportFormat.PDF.value == "pdf"
        assert ExportFormat.EXCEL.value == "xlsx"

    def test_export_formats_are_distinct(self) -> None:
        """Test that all export formats have distinct values."""
        values = [f.value for f in ExportFormat]
        assert len(values) == len(set(values))


class TestAbstractExporter:
    """Tests for AbstractExporter base class."""

    def test_get_content_type_json(self) -> None:
        """Test content type for JSON format."""
        exporter = TestJsonExporter()
        assert exporter.get_content_type() == "application/json"

    def test_get_content_type_csv(self) -> None:
        """Test content type for CSV format."""
        exporter = TestCsvExporter()
        assert exporter.get_content_type() == "text/csv"

    def test_get_file_extension_json(self) -> None:
        """Test file extension for JSON format."""
        exporter = TestJsonExporter()
        assert exporter.get_file_extension() == "json"

    def test_get_file_extension_csv(self) -> None:
        """Test file extension for CSV format."""
        exporter = TestCsvExporter()
        assert exporter.get_file_extension() == "csv"

    @pytest.mark.anyio
    async def test_generate_json(self) -> None:
        """Test JSON generation."""
        exporter = TestJsonExporter()
        data = [{"id": 1, "name": "test"}]
        result = await exporter.generate(data)
        assert result == b'[{"id": 1, "name": "test"}]'

    @pytest.mark.anyio
    async def test_generate_csv(self) -> None:
        """Test CSV generation."""
        exporter = TestCsvExporter()
        result = await exporter.generate([])
        assert result == b"csv,data"

    def test_export_type_property(self) -> None:
        """Test export_type property."""
        exporter = TestJsonExporter()
        assert exporter.export_type == ExportType.REPORT

    def test_export_format_property(self) -> None:
        """Test export_format property."""
        exporter = TestJsonExporter()
        assert exporter.export_format == ExportFormat.JSON


class TestExportRegistry:
    """Tests for ExportRegistry."""

    def setup_method(self) -> None:
        """Clear registry before each test."""
        ExportRegistry._exporters.clear()

    def test_register_decorator(self) -> None:
        """Test that @register decorator registers exporter."""

        @ExportRegistry.register(ExportType.REPORT, ExportFormat.JSON)
        class MyExporter(AbstractExporter[dict]):
            @property
            def export_type(self) -> ExportType:
                return ExportType.REPORT

            @property
            def export_format(self) -> ExportFormat:
                return ExportFormat.JSON

            async def generate(self, data: dict, options: dict | None = None) -> bytes:
                return b""

        assert ExportRegistry.has_exporter(ExportType.REPORT, ExportFormat.JSON)
        assert ExportRegistry.get_exporter(ExportType.REPORT, ExportFormat.JSON) is MyExporter

    def test_register_multiple_exporters(self) -> None:
        """Test registering multiple exporters."""

        @ExportRegistry.register(ExportType.REPORT, ExportFormat.JSON)
        class ReportJsonExporter(AbstractExporter[dict]):
            @property
            def export_type(self) -> ExportType:
                return ExportType.REPORT

            @property
            def export_format(self) -> ExportFormat:
                return ExportFormat.JSON

            async def generate(self, data: dict, options: dict | None = None) -> bytes:
                return b""

        @ExportRegistry.register(ExportType.DATA, ExportFormat.CSV)
        class DataCsvExporter(AbstractExporter[list]):
            @property
            def export_type(self) -> ExportType:
                return ExportType.DATA

            @property
            def export_format(self) -> ExportFormat:
                return ExportFormat.CSV

            async def generate(self, data: list, options: dict | None = None) -> bytes:
                return b""

        assert ExportRegistry.has_exporter(ExportType.REPORT, ExportFormat.JSON)
        assert ExportRegistry.has_exporter(ExportType.DATA, ExportFormat.CSV)
        assert len(ExportRegistry.list_exporters()) == 2

    def test_get_exporter_not_found(self) -> None:
        """Test getting non-existent exporter returns None."""
        result = ExportRegistry.get_exporter(ExportType.AUDIT, ExportFormat.PDF)
        assert result is None

    def test_has_exporter_false(self) -> None:
        """Test has_exporter returns False for non-existent exporter."""
        assert not ExportRegistry.has_exporter(ExportType.SUMMARY, ExportFormat.HTML)

    def test_list_exporters_empty(self) -> None:
        """Test list_exporters on empty registry."""
        assert ExportRegistry.list_exporters() == []

    def test_list_exporters_returns_tuples(self) -> None:
        """Test list_exporters returns correct tuples."""

        @ExportRegistry.register(ExportType.REPORT, ExportFormat.JSON)
        class DummyExporter(AbstractExporter[dict]):
            @property
            def export_type(self) -> ExportType:
                return ExportType.REPORT

            @property
            def export_format(self) -> ExportFormat:
                return ExportFormat.JSON

            async def generate(self, data: dict, options: dict | None = None) -> bytes:
                return b""

        exporters = ExportRegistry.list_exporters()
        assert len(exporters) == 1
        assert exporters[0] == (ExportType.REPORT, ExportFormat.JSON)

    def test_register_overwrites_existing(self) -> None:
        """Test that registering same key overwrites previous exporter."""

        @ExportRegistry.register(ExportType.REPORT, ExportFormat.JSON)
        class FirstExporter(AbstractExporter[dict]):
            @property
            def export_type(self) -> ExportType:
                return ExportType.REPORT

            @property
            def export_format(self) -> ExportFormat:
                return ExportFormat.JSON

            async def generate(self, data: dict, options: dict | None = None) -> bytes:
                return b"first"

        @ExportRegistry.register(ExportType.REPORT, ExportFormat.JSON)
        class SecondExporter(AbstractExporter[dict]):
            @property
            def export_type(self) -> ExportType:
                return ExportType.REPORT

            @property
            def export_format(self) -> ExportFormat:
                return ExportFormat.JSON

            async def generate(self, data: dict, options: dict | None = None) -> bytes:
                return b"second"

        exporter_class = ExportRegistry.get_exporter(ExportType.REPORT, ExportFormat.JSON)
        assert exporter_class is SecondExporter

    @pytest.mark.anyio
    async def test_registered_exporter_can_generate(self) -> None:
        """Test that registered exporter can be instantiated and used."""

        @ExportRegistry.register(ExportType.SUMMARY, ExportFormat.HTML)
        class HtmlSummaryExporter(AbstractExporter[str]):
            @property
            def export_type(self) -> ExportType:
                return ExportType.SUMMARY

            @property
            def export_format(self) -> ExportFormat:
                return ExportFormat.HTML

            async def generate(self, data: str, options: dict | None = None) -> bytes:
                return f"<html><body>{data}</body></html>".encode()

        exporter_class = ExportRegistry.get_exporter(ExportType.SUMMARY, ExportFormat.HTML)
        assert exporter_class is not None

        exporter = exporter_class()
        result = await exporter.generate("Hello World")
        assert result == b"<html><body>Hello World</body></html>"
