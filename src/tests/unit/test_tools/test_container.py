import shutil

import pytest
from _pytest.monkeypatch import MonkeyPatch

from tools.lib.container import ContainerRuntime, ContainerRuntimeError


def test_detect_docker(monkeypatch: MonkeyPatch) -> None:
    def mock_which(cmd: str) -> str | None:
        if cmd == "docker":
            return "/usr/bin/docker"
        return None
    monkeypatch.setattr(shutil, "which", mock_which)

    runtime = ContainerRuntime()
    assert runtime.name == "docker"
    assert runtime.path == "/usr/bin/docker"

def test_detect_podman(monkeypatch: MonkeyPatch) -> None:
    def mock_which(cmd: str) -> str | None:
        if cmd == "podman":
            return "/usr/bin/podman"
        return None
    monkeypatch.setattr(shutil, "which", mock_which)

    runtime = ContainerRuntime()
    assert runtime.name == "podman"
    assert runtime.path == "/usr/bin/podman"

def test_detect_none(monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setattr(shutil, "which", lambda _: None)

    with pytest.raises(ContainerRuntimeError):
        ContainerRuntime()
