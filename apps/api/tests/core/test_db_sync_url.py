from app.core.db_sync import to_sync_url


def test_asyncpg_scheme_is_coerced_to_psycopg() -> None:
    assert to_sync_url("postgresql+asyncpg://u:p@h:5432/db") == "postgresql+psycopg://u:p@h:5432/db"


def test_postgresql_scheme_is_coerced_to_psycopg() -> None:
    assert to_sync_url("postgresql://u:p@h:5432/db") == "postgresql+psycopg://u:p@h:5432/db"


def test_psycopg_scheme_is_passed_through_unchanged() -> None:
    url = "postgresql+psycopg://u:p@h:5432/db"
    assert to_sync_url(url) == url
