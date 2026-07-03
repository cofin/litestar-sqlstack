from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from tools.cli.infra import infra_group


@pytest.fixture
def mock_db() -> MagicMock:
    return MagicMock()

def test_infra_start(mock_db: MagicMock) -> None:
    runner = CliRunner()
    with patch("tools.cli.infra.PostgreSQLDatabase", return_value=mock_db), \
         patch("tools.cli.infra.ContainerRuntime"):
        result = runner.invoke(infra_group, ["start"])
        assert result.exit_code == 0
        assert mock_db.start.call_count == 1

def test_infra_stop(mock_db: MagicMock) -> None:
    runner = CliRunner()
    with patch("tools.cli.infra.PostgreSQLDatabase", return_value=mock_db), \
         patch("tools.cli.infra.ContainerRuntime"):
        result = runner.invoke(infra_group, ["stop"])
        assert result.exit_code == 0
        assert mock_db.stop.call_count == 1

def test_infra_status(mock_db: MagicMock) -> None:
    runner = CliRunner()
    mock_db.status.return_value = "running"
    with patch("tools.cli.infra.PostgreSQLDatabase", return_value=mock_db), \
         patch("tools.cli.infra.ContainerRuntime"):
        result = runner.invoke(infra_group, ["status"])
        assert result.exit_code == 0
        assert "running" in result.output
