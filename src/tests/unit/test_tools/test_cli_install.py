from unittest.mock import MagicMock, patch

from click.testing import CliRunner

from tools.cli.install import install_command


def test_install_command_success() -> None:
    runner = CliRunner()

    with patch("shutil.which", return_value=None), \
         patch("subprocess.run") as mock_run:

        mock_run.return_value = MagicMock(returncode=0)
        result = runner.invoke(install_command)

        assert result.exit_code == 0

        assert mock_run.call_count == 3

        calls = [args[0] for args, _ in mock_run.call_args_list]
        assert ["uv", "sync", "--all-extras", "--dev"] in calls
        assert ["uvx", "nodeenv", ".venv", "--force", "--quiet"] in calls
        assert ["uv", "run", "pre-commit", "install"] in calls

def test_install_command_has_npm() -> None:
    runner = CliRunner()

    with patch("shutil.which", side_effect=lambda cmd: "/usr/bin/npm" if cmd == "npm" else None), \
         patch("subprocess.run") as mock_run:

        mock_run.return_value = MagicMock(returncode=0)
        result = runner.invoke(install_command)

        assert result.exit_code == 0

        assert mock_run.call_count == 2
        calls = [args[0] for args, _ in mock_run.call_args_list]
        assert ["uv", "sync", "--all-extras", "--dev"] in calls
        assert ["uv", "run", "pre-commit", "install"] in calls
        assert not any("nodeenv" in c for c in calls)
