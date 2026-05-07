from sqlalchemy import create_engine
from sqlalchemy.engine.url import make_url
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings


def to_sync_url(url: str) -> str:
    parsed = make_url(url)
    if parsed.drivername in {"postgresql+asyncpg", "postgresql"}:
        parsed = parsed.set(drivername="postgresql+psycopg")
    return parsed.render_as_string(hide_password=False)


sync_engine = create_engine(
    to_sync_url(get_settings().database_url),
    echo=False,
    future=True,
)

SyncSessionLocal: sessionmaker[Session] = sessionmaker(sync_engine, expire_on_commit=False)
