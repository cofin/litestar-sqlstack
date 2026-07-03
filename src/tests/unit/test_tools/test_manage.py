from click.testing import CliRunner
from manage import manage_cli

def test_manage_cli_help():
    runner = CliRunner()
    result = runner.invoke(manage_cli, ["--help"])
    
    assert result.exit_code == 0
    assert "init" in result.output
    assert "doctor" in result.output
    assert "install" in result.output
    assert "infra" in result.output
