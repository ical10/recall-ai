from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from app.core.db import SessionLocal, engine


def test_engine_is_async_and_uses_asyncpg():
    assert isinstance(engine, AsyncEngine)
    assert "asyncpg" in str(engine.url)


def test_sessionmaker_yields_async_sessions():
    assert isinstance(SessionLocal, async_sessionmaker)
    assert SessionLocal.class_ is AsyncSession
