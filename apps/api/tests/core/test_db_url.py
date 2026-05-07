from app.core.db import to_async_url


def test_postgresql_scheme_is_coerced_to_asyncpg() -> None:
    assert to_async_url("postgresql://u:p@h:5432/db") == "postgresql+asyncpg://u:p@h:5432/db"


def test_psycopg2_scheme_is_coerced_to_asyncpg() -> None:
    assert (
        to_async_url("postgresql+psycopg2://u:p@h:5432/db") == "postgresql+asyncpg://u:p@h:5432/db"
    )


def test_asyncpg_scheme_is_passed_through_unchanged() -> None:
    url = "postgresql+asyncpg://u:p@h:5432/db"
    assert to_async_url(url) == url
