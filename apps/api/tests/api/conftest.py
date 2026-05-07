from collections.abc import AsyncIterator, Iterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine


@pytest.fixture
def probe_app(tmp_path: Path) -> Iterator[FastAPI]:
    from app.api.deps import (
        DEV_USER_EMAIL,
        DEV_USER_GOOGLE_ID,
        DEV_USER_NAME,
        get_current_user,
    )
    from app.core.db import get_session
    from app.models import Base
    from app.models.user import User

    db_path = tmp_path / "test.db"
    engine = create_async_engine(f"sqlite+aiosqlite:///{db_path}", future=True)
    factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        yield
        await engine.dispose()

    app = FastAPI(lifespan=lifespan)

    async def override_get_session() -> AsyncIterator[AsyncSession]:
        async with factory() as session:
            yield session

    app.dependency_overrides[get_session] = override_get_session

    SessionDep = Annotated[AsyncSession, Depends(override_get_session)]
    UserDep = Annotated[User, Depends(get_current_user)]

    @app.get("/_probe")
    async def probe(user: UserDep) -> dict[str, str]:
        return {"id": str(user.id), "email": user.email}

    @app.get("/_user_count")
    async def user_count(session: SessionDep) -> dict[str, int]:
        result = await session.execute(select(func.count()).select_from(User))
        return {"count": int(result.scalar_one())}

    @app.post("/_seed_dev_user")
    async def seed_dev_user(session: SessionDep) -> dict[str, str]:
        user = User(
            email=DEV_USER_EMAIL,
            google_id=DEV_USER_GOOGLE_ID,
            name=DEV_USER_NAME,
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)
        return {"id": str(user.id)}

    yield app


@pytest.fixture
def probe_client(probe_app: FastAPI) -> Iterator[TestClient]:
    with TestClient(probe_app) as client:
        yield client
