from unittest.mock import MagicMock, patch
from click.testing import CliRunner
import pytest
from tools.cli.clean import clean_command
from tools.cli.destroy import destroy_command

def test_clean_command():
    runner = CliRunner()
    with patch("tools.cli.clean.Path") as mock_path:
        result = runner.invoke(clean_command)
        assert result.exit_code == 0
        assert "cleaned" in result.output

def test_destroy_command():
    runner = CliRunner()
    with patch("tools.cli.destroy.Path") as mock_path:
        result = runner.invoke(destroy_command)
        assert result.exit_code == 0
        assert "destroyed" in result.output or "No virtual environment found" in result.output
