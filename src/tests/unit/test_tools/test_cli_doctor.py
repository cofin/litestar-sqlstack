from unittest.mock import MagicMock, patch

from click.testing import CliRunner

from tools.cli.doctor import doctor_command
from tools.lib.container import ContainerRuntimeError


def test_doctor_missing_runtime() -> None:
    runner = CliRunner()
    with patch("tools.cli.doctor.ContainerRuntime", side_effect=ContainerRuntimeError("No runtime")):
        result = runner.invoke(doctor_command)
        assert result.exit_code != 0
        assert "No container runtime detected" in result.output

def test_doctor_port_in_use() -> None:
    runner = CliRunner()
    mock_runtime = MagicMock()
    mock_runtime.name = "docker"

    with patch("tools.cli.doctor.ContainerRuntime", return_value=mock_runtime), \
         patch("tools.cli.doctor.is_port_in_use", return_value=True):
        result = runner.invoke(doctor_command)
        assert result.exit_code != 0
        assert "Port 15432 is already in use" in result.output

def test_doctor_success() -> None:
    runner = CliRunner()
    mock_runtime = MagicMock()
    mock_runtime.name = "docker"

    with patch("tools.cli.doctor.ContainerRuntime", return_value=mock_runtime), \
         patch("tools.cli.doctor.is_port_in_use", return_value=False):
        result = runner.invoke(doctor_command)
        assert result.exit_code == 0
        assert "Container runtime: docker" in result.output
        assert "Database port 15432 is available" in result.output
