import subprocess
import time
from dataclasses import dataclass

import psycopg

from tools.lib.container import ContainerRuntime
from tools.lib.db_url import make_postgres_url


@dataclass
class DatabaseConfig:
    """Configuration for the PostgreSQL database container."""

    container_name: str = "sqlstack-db"
    port: int = 15432
    image: str = "postgres:16-alpine"
    user: str = "app"
    password: str = "super-secret"
    database: str = "app"


class PostgreSQLDatabase:
    """Manages the PostgreSQL database container lifecycle."""

    def __init__(self, runtime: ContainerRuntime, config: DatabaseConfig | None = None) -> None:
        self.runtime = runtime
        self.config = config or DatabaseConfig()

    def status(self) -> str:
        """Get the status of the container."""
        try:
            result = self.runtime.run(
                ["ps", "-a", "--filter", f"name=^{self.config.container_name}$", "--format", "{{.State}}"],
                capture_output=True,
            )
            stdout = result.stdout.strip()
            if not stdout:
                return "non-existent"
            if stdout == "running":
                return "running"
            return "stopped"
        except (subprocess.SubprocessError, OSError):
            return "unknown"

    @staticmethod
    def verify_connection(url: str) -> bool:
        """Verify the wire connection by attempting to connect and run a query."""
        try:
            with psycopg.connect(url, connect_timeout=3) as conn, conn.cursor() as cur:
                cur.execute("SELECT 1")
                return True
        except (psycopg.Error, OSError):
            return False

    def wait_for_ready(self, timeout: int = 30) -> bool:
        """Wait for the database container to accept connections."""
        url = make_postgres_url(
            user=self.config.user,
            password=self.config.password,
            host="localhost",
            port=self.config.port,
            database=self.config.database,
        )
        start_time = time.time()
        while time.time() - start_time < timeout:
            if self.verify_connection(url):
                return True
            time.sleep(0.5)
        return False

    def start(self) -> None:
        """Start the container."""
        current_status = self.status()
        if current_status == "running":
            return
        if current_status == "stopped":
            self.runtime.run(["start", self.config.container_name])
        else:
            self.runtime.run([
                "run", "-d",
                "--name", self.config.container_name,
                "-p", f"{self.config.port}:5432",
                "-e", f"POSTGRES_USER={self.config.user}",
                "-e", f"POSTGRES_PASSWORD={self.config.password}",
                "-e", f"POSTGRES_DB={self.config.database}",
                self.config.image,
            ])
        if not self.wait_for_ready():
            raise RuntimeError("Database container failed to start/become ready.")

    def stop(self) -> None:
        """Stop the container."""
        if self.status() == "running":
            self.runtime.run(["stop", self.config.container_name])

    def restart(self) -> None:
        """Restart the container."""
        self.runtime.run(["restart", self.config.container_name])
        if not self.wait_for_ready():
            raise RuntimeError("Database container failed to become ready after restart.")

    def remove(self) -> None:
        """Remove the container."""
        self.runtime.run(["rm", "-f", self.config.container_name])
