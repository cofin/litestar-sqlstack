from __future__ import annotations

import gzip
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any, Self

import msgspec
import pytest

from sqlstack.utils.fixtures import FixtureExporter, FixtureLoader, FixtureProcessor

if TYPE_CHECKING:
    from inspect import Traceback


def write_fixture(path: Path, payload: list[dict[str, Any]], compress: bool = False) -> Path:
    data = msgspec.json.encode(payload)
    if compress:
        with gzip.open(path, "wb") as fh:
            fh.write(data)
    else:
        path.write_bytes(data)
    return path


def test_load_fixture_data_handles_compressed_files(tmp_path: Path) -> None:
    fixtures_dir = tmp_path / "fixtures"
    fixtures_dir.mkdir()

    payload = [{"id": "1", "name": "Alice"}, {"id": "2", "name": "Bob"}]
    gz_path = fixtures_dir / "users.json.gz"
    write_fixture(gz_path, payload, compress=True)

    processor = FixtureProcessor(fixtures_dir)
    data = processor.load_fixture_data(gz_path)

    assert data == payload


def test_prepare_record_converts_timestamps_and_ignores_none(tmp_path: Path) -> None:
    processor = FixtureProcessor(tmp_path)
    iso_timestamp = "2024-01-01T12:34:56+00:00"
    record = {"id": "1", "created_at": iso_timestamp, "name": None, "count": 3}

    prepared = processor.prepare_record(record)

    assert prepared == {"id": "1", "created_at": datetime.fromisoformat(iso_timestamp), "count": 3}


def test_get_fixture_files_respects_table_order(tmp_path: Path) -> None:
    fixtures_dir = tmp_path / "fixtures"
    fixtures_dir.mkdir()

    write_fixture(fixtures_dir / "teams.json", [])
    write_fixture(fixtures_dir / "users.json", [])

    processor = FixtureProcessor(fixtures_dir)
    ordered_files = processor.get_fixture_files(["users", "teams"])

    assert [f.name for f in ordered_files] == ["users.json", "teams.json"]


def test_generate_missing_fixture_results(tmp_path: Path) -> None:
    _processor = FixtureProcessor(tmp_path)
    loader = FixtureLoader(tmp_path, driver=object(), table_order=["users", "teams"])

    missing = loader._generate_missing_fixtures_results()

    assert missing == {
        "users": "Error: Could not find the users fixture",
        "teams": "Error: Could not find the teams fixture",
    }


class DummyTransaction:
    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(
        self, exc_type: type[BaseException] | None, exc: BaseException | None, tb: Traceback | None
    ) -> None:
        return None


class DummyConnection:
    def transaction(self) -> DummyTransaction:
        return DummyTransaction()


class DummyDriver:
    def __init__(self) -> None:
        self.connection = DummyConnection()
        self.calls: list[tuple[str, list[tuple[Any, ...]]]] = []

    async def execute_many(self, sql: str, params: list[tuple[Any, ...]]) -> None:
        self.calls.append((sql.strip(), params))


@pytest.mark.anyio
async def test_fixture_loader_upserts_records(tmp_path: Path) -> None:
    fixtures_dir = tmp_path / "fixtures"
    fixtures_dir.mkdir()

    payload = [
        {"id": "1", "name": "Alice", "created_at": "2024-01-01T00:00:00+00:00"},
        {"id": "2", "name": "Bob", "last_activity": "2024-01-02T00:00:00+00:00"},
    ]
    write_fixture(fixtures_dir / "users.json", payload)

    driver = DummyDriver()
    loader = FixtureLoader(fixtures_dir, driver=driver, table_order=["users"])

    results = await loader.load_all_fixtures()

    assert results == {"users": {"upserted": 2, "failed": 0, "total": 2}}
    assert len(driver.calls) == 1
    executed_sql, params = driver.calls[0]
    assert "ON CONFLICT" in executed_sql
    assert params == [
        (datetime(2024, 1, 1, 0, 0, tzinfo=UTC), "1", None, "Alice"),
        (None, "2", datetime(2024, 1, 2, 0, 0, tzinfo=UTC), "Bob"),
    ]


@pytest.mark.anyio
async def test_fixture_loader_requires_id_column(tmp_path: Path) -> None:
    fixtures_dir = tmp_path / "fixtures"
    fixtures_dir.mkdir()

    payload = [{"name": "Missing Id"}]
    write_fixture(fixtures_dir / "users.json", payload)

    loader = FixtureLoader(fixtures_dir, driver=DummyDriver(), table_order=["users"])

    results = await loader.load_all_fixtures()

    assert results == {"users": "Error: Fixture records must have an 'id' column for upserting."}


class ExportDriver:
    def __init__(self, records: list[dict[str, Any]]) -> None:
        self.records = records

    async def select(self, query: Any) -> list[dict[str, Any]]:
        return self.records


@pytest.mark.anyio
async def test_fixture_exporter_writes_gzipped_files(tmp_path: Path) -> None:
    fixtures_dir = tmp_path / "fixtures"
    fixtures_dir.mkdir()

    driver = ExportDriver([{"id": "1", "created_at": datetime(2024, 1, 1, 0, 0, tzinfo=UTC), "payload": b"data"}])

    exporter = FixtureExporter(fixtures_dir, driver=driver, table_order=["users"])

    results = await exporter.export_all_fixtures()

    output_path = Path(results["users"])
    assert output_path.exists()

    with gzip.open(output_path, "rb") as fh:
        decoded = msgspec.json.decode(fh.read())

    assert decoded == [{"id": "1", "created_at": "2024-01-01T00:00:00+00:00", "payload": "data"}]


@pytest.mark.anyio
async def test_fixture_exporter_handles_empty_tables(tmp_path: Path) -> None:
    exporter = FixtureExporter(tmp_path, driver=ExportDriver([]), table_order=["users"])

    result = await exporter._export_table("users", tmp_path, compress=False)

    assert result == "No data found"
