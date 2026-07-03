import shutil
import subprocess
from collections.abc import Sequence
from typing import Any


class ContainerRuntimeError(Exception):
    """Raised when container runtime detection or execution fails."""

class ContainerRuntime:
    """Detects and wraps the container runtime (Docker or Podman)."""

    def __init__(self) -> None:
        self.name: str = ""
        self.path: str = ""
        self._detect()

    def _detect(self) -> None:
        for engine in ("docker", "podman"):
            path = shutil.which(engine)
            if path:
                self.name = engine
                self.path = path
                return
        raise ContainerRuntimeError("No container runtime (docker or podman) detected in PATH.")

    def run(
        self,
        args: Sequence[str],
        check: bool = True,
        capture_output: bool = False,
        text: bool = True,
        **kwargs: Any,
    ) -> subprocess.CompletedProcess[str]:
        cmd = [self.path, *args]
        return subprocess.run(
            cmd,
            check=check,
            capture_output=capture_output,
            text=text,
            **kwargs,
        )
