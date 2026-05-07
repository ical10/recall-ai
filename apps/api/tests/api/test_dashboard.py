from collections.abc import AsyncIterator, Iterator
from contextlib import asynccontextmanager
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.db import get_session
from app.models import Base


@pytest.fixture
def dashboard_app(tmp_path: Path) -> Iterator[FastAPI]:
    db_path = tmp_path / "test.db"
    engine = create_async_engine(f"sqlite+aiosqlite:///{db_path}", future=True)
    factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        yield
        await engine.dispose()

    from app.api.dashboard import router

    app = FastAPI(lifespan=lifespan)

    async def override_get_session() -> AsyncIterator[AsyncSession]:
        async with factory() as session:
            yield session

    app.dependency_overrides[get_session] = override_get_session
    app.include_router(router)

    yield app


@pytest.fixture
def dashboard_client(dashboard_app: FastAPI) -> Iterator[TestClient]:
    with TestClient(dashboard_app, follow_redirects=False) as client:
        yield client


def test_index_redirects_to_dashboard(dashboard_client: TestClient) -> None:
    response = dashboard_client.get("/")
    assert response.status_code == 307
    assert response.headers["location"] == "/dashboard"


def test_dashboard_returns_200(dashboard_client: TestClient) -> None:
    response = dashboard_client.get("/dashboard")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]


def test_dashboard_contains_stats_headings(dashboard_client: TestClient) -> None:
    response = dashboard_client.get("/dashboard")
    assert response.status_code == 200
    body = response.text
    assert "Due today" in body
    assert "Total reviews" in body
    assert "Streak" in body
