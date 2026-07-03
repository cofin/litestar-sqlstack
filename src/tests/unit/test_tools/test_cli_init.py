from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

from tools.cli.init import init_env


def test_init_env_creates_env_file(tmp_path: Path) -> None:
    env_example = tmp_path / ".env.example"
    env_example.write_text("SECRET_KEY=placeholder\nOTHER_VAR=value")

    with patch("tools.cli.init.Path.exists", side_effect=lambda: False), \
         patch("tools.cli.init.Path") as mock_path_cls:

        example_mock = MagicMock()
        example_mock.exists.return_value = True
        example_mock.read_text.return_value = "SECRET_KEY=placeholder\nOTHER_VAR=value"

        env_mock = MagicMock()
        env_mock.exists.return_value = False

        def path_side_effect(path_str: Any) -> MagicMock:
            if ".env.example" in str(path_str):
                return example_mock
            if ".env" in str(path_str):
                return env_mock
            return MagicMock()

        mock_path_cls.side_effect = path_side_effect

        init_env(env_file=env_mock, example_file=example_mock)

        assert env_mock.write_text.call_count == 1
        written_content = env_mock.write_text.call_args[0][0]
        assert "SECRET_KEY=" in written_content
        assert "placeholder" not in written_content
        assert "OTHER_VAR=value" in written_content
