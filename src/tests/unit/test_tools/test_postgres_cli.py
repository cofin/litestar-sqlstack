from unittest.mock import MagicMock, patch
from click.testing import CliRunner
import pytest
from tools.postgres.cli.connection import test_connection_cmd
from tools.postgres.cli.database import create_db_cmd, drop_db_cmd
from tools.postgres.cli.health import health_cmd

@pytest.fixture
def mock_settings():
    settings = MagicMock()
    settings.db.USER = "app"
    settings.db.PASSWORD = "super-secret"
    settings.db.HOST = "localhost"
    settings.db.PORT = 15432
    settings.db.DATABASE = "app"
    settings.db.get_connection_string.return_value = "postgresql://app:super-secret@localhost:15432/app"
    return settings

def test_connection_success(mock_settings):
    runner = CliRunner()
    with patch("tools.postgres.cli.connection.get_settings", return_value=mock_settings), \
         patch("tools.postgres.cli.connection.PostgreSQLDatabase.verify_connection", return_value=True):
        result = runner.invoke(test_connection_cmd)
        assert result.exit_code == 0
        assert "Connection successful" in result.output

def test_connection_failed(mock_settings):
    runner = CliRunner()
    with patch("tools.postgres.cli.connection.get_settings", return_value=mock_settings), \
         patch("tools.postgres.cli.connection.PostgreSQLDatabase.verify_connection", return_value=False):
        result = runner.invoke(test_connection_cmd)
        assert result.exit_code != 0
        assert "Connection failed" in result.output

def test_create_db_already_exists(mock_settings):
    runner = CliRunner()
    mock_conn = MagicMock()
    mock_cur = MagicMock()
    mock_cur.fetchone.return_value = (1,)
    mock_conn.__enter__.return_value = mock_conn
    mock_conn.cursor.return_value.__enter__.return_value = mock_cur
    
    with patch("tools.postgres.cli.database.get_settings", return_value=mock_settings), \
         patch("psycopg.connect", return_value=mock_conn):
        result = runner.invoke(create_db_cmd)
        assert result.exit_code == 0
        assert "already exists" in result.output

def test_create_db_success(mock_settings):
    runner = CliRunner()
    mock_conn = MagicMock()
    mock_cur = MagicMock()
    mock_cur.fetchone.return_value = None
    mock_conn.__enter__.return_value = mock_conn
    mock_conn.cursor.return_value.__enter__.return_value = mock_cur
    
    with patch("tools.postgres.cli.database.get_settings", return_value=mock_settings), \
         patch("psycopg.connect", return_value=mock_conn):
        result = runner.invoke(create_db_cmd)
        assert result.exit_code == 0
        assert "created successfully" in result.output

def test_drop_db_success(mock_settings):
    runner = CliRunner()
    mock_conn = MagicMock()
    mock_conn.__enter__.return_value = mock_conn
    
    with patch("tools.postgres.cli.database.get_settings", return_value=mock_settings), \
         patch("psycopg.connect", return_value=mock_conn):
        result = runner.invoke(drop_db_cmd, ["--yes"])
        assert result.exit_code == 0
        assert "dropped" in result.output

def test_health_success(mock_settings):
    runner = CliRunner()
    with patch("tools.postgres.cli.health.get_settings", return_value=mock_settings), \
         patch("tools.postgres.cli.health.PostgreSQLDatabase.verify_connection", return_value=True):
        result = runner.invoke(health_cmd)
        assert result.exit_code == 0
        assert "wire connection is healthy" in result.output
