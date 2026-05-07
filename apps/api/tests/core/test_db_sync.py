from sqlalchemy import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.db_sync import SyncSessionLocal, sync_engine


def test_sync_engine_is_engine_and_uses_psycopg() -> None:
    assert isinstance(sync_engine, Engine)
    assert "psycopg" in str(sync_engine.url)


def test_sessionmaker_yields_sync_sessions() -> None:
    assert isinstance(SyncSessionLocal, sessionmaker)
    assert issubclass(SyncSessionLocal.class_, Session)
