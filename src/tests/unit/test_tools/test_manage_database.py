from click.testing import CliRunner
from manage import database_group

def test_database_group_help():
    runner = CliRunner()
    result = runner.invoke(database_group, ["--help"])
    
    assert result.exit_code == 0
    # Ported commands
    assert "test-connection" in result.output
    assert "create-db" in result.output
    assert "drop-db" in result.output
    assert "health" in result.output
    # Migration commands from sqlspec
    assert "upgrade" in result.output
    assert "downgrade" in result.output
    assert "create-migration" in result.output
