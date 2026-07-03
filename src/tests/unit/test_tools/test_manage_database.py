from click.testing import CliRunner
from manage import database_group


def test_database_group_help() -> None:
    runner = CliRunner()
    result = runner.invoke(database_group, ["--help"])

    assert result.exit_code == 0
    assert "test-connection" in result.output
    assert "create-db" in result.output
    assert "drop-db" in result.output
    assert "health" in result.output
    assert "upgrade" in result.output
    assert "downgrade" in result.output
    assert "create-migration" in result.output
