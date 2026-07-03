from unittest.mock import MagicMock
import shutil
import pytest
from tools.lib.container import ContainerRuntime, ContainerRuntimeError

def test_detect_docker(monkeypatch):
    def mock_which(cmd):
        if cmd == "docker":
            return "/usr/bin/docker"
        return None
    monkeypatch.setattr(shutil, "which", mock_which)

    runtime = ContainerRuntime()
    assert runtime.name == "docker"
    assert runtime.path == "/usr/bin/docker"

def test_detect_podman(monkeypatch):
    def mock_which(cmd):
        if cmd == "podman":
            return "/usr/bin/podman"
        return None
    monkeypatch.setattr(shutil, "which", mock_which)

    runtime = ContainerRuntime()
    assert runtime.name == "podman"
    assert runtime.path == "/usr/bin/podman"

def test_detect_none(monkeypatch):
    monkeypatch.setattr(shutil, "which", lambda cmd: None)

    with pytest.raises(ContainerRuntimeError):
        ContainerRuntime()
