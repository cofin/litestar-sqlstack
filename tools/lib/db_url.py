import urllib.parse


def make_postgres_url(
    *,
    driver: str | None = None,
    user: str = "app",
    password: str = "super-secret",
    host: str = "localhost",
    port: int = 5432,
    database: str = "app",
) -> str:
    """Build a standard PostgreSQL connection string."""
    scheme = driver or "postgresql"
    safe_password = urllib.parse.quote_plus(password)
    return f"{scheme}://{user}:{safe_password}@{host}:{port}/{database}"
