from tools.lib.db_url import make_postgres_url

def test_make_postgres_url_defaults():
    url = make_postgres_url()
    assert url == "postgresql://app:super-secret@localhost:5432/app"

def test_make_postgres_url_custom():
    url = make_postgres_url(
        driver="postgresql+asyncpg",
        user="custom_user",
        password="custom_password",
        host="db.example.com",
        port=15432,
        database="custom_db",
    )
    assert url == "postgresql+asyncpg://custom_user:custom_password@db.example.com:15432/custom_db"
