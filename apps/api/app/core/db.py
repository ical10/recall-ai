from collections.abc import AsyncIterator

from sqlalchemy.engine.url import make_url
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import get_settings


def to_async_url(url: str) -> str:
    parsed = make_url(url)
    if parsed.drivername in {"postgresql", "postgresql+psycopg2", "postgresql+psycopg"}:
        parsed = parsed.set(drivername="postgresql+asyncpg")
    return parsed.render_as_string(hide_password=False)


engine: AsyncEngine = create_async_engine(
    to_async_url(get_settings().database_url),
    echo=False,
    future=True,
)

SessionLocal = async_sessionmaker(engine, expire_on_commit=False)


async def get_session() -> AsyncIterator[AsyncSession]:
    async with SessionLocal() as session:
        yield session
