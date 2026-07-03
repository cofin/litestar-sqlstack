from unittest.mock import MagicMock, patch
import pytest
from tools.postgres.database import PostgreSQLDatabase, DatabaseConfig
from tools.lib.container import ContainerRuntime

@pytest.fixture
def mock_runtime():
    runtime = MagicMock(spec=ContainerRuntime)
    runtime.path = "/usr/bin/docker"
    runtime.name = "docker"
    return runtime

def test_database_start_not_exists(mock_runtime):
    db_config = DatabaseConfig(container_name="test-db", port=15432)
    db = PostgreSQLDatabase(runtime=mock_runtime, config=db_config)

    with patch("tools.postgres.database.PostgreSQLDatabase.status", return_value="non-existent"), \
         patch("tools.postgres.database.PostgreSQLDatabase.verify_connection", return_value=True):
        db.start()

    assert mock_runtime.run.call_count == 1
    args, kwargs = mock_runtime.run.call_args
    assert "run" in args[0]
    assert "--name" in args[0]
    assert "test-db" in args[0]
    assert "15432:5432" in args[0]

def test_database_start_stopped(mock_runtime):
    db_config = DatabaseConfig(container_name="test-db", port=15432)
    db = PostgreSQLDatabase(runtime=mock_runtime, config=db_config)

    with patch("tools.postgres.database.PostgreSQLDatabase.status", return_value="stopped"), \
         patch("tools.postgres.database.PostgreSQLDatabase.verify_connection", return_value=True):
        db.start()

    assert mock_runtime.run.call_count == 1
    args, kwargs = mock_runtime.run.call_args
    assert "start" in args[0]
    assert "test-db" in args[0]

def test_database_stop(mock_runtime):
    db_config = DatabaseConfig(container_name="test-db", port=15432)
    db = PostgreSQLDatabase(runtime=mock_runtime, config=db_config)

    with patch("tools.postgres.database.PostgreSQLDatabase.status", return_value="running"):
        db.stop()

    assert mock_runtime.run.call_count == 1
    args, kwargs = mock_runtime.run.call_args
    assert "stop" in args[0]
    assert "test-db" in args[0]
