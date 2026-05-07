import asyncio
import uuid
from collections.abc import AsyncIterator, Callable, Iterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import UTC
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.api.deps import get_current_user
from app.api.vocab import router as vocab_router
from app.core.db import get_session
from app.models import Base
from app.models.user import User
from app.models.vocab_item import VocabItem


@dataclass
class VocabFixture:
    client: TestClient
    user_id: uuid.UUID
    run: Callable[[Callable[[AsyncSession], object]], object]


@pytest.fixture
def vocab_fixture(tmp_path: Path) -> Iterator[VocabFixture]:
    db_path = tmp_path / "test.db"
    engine = create_async_engine(f"sqlite+aiosqlite:///{db_path}", future=True)

    @event.listens_for(engine.sync_engine, "connect")
    def _enable_sqlite_fk(dbapi_connection: object, _conn_record: object) -> None:
        cursor = dbapi_connection.cursor()  # type: ignore[attr-defined]
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

    test_user = User(
        id=uuid.uuid4(),
        email="test@local",
        google_id="test-local",
        name="Test",
    )

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        async with factory() as session:
            session.add(test_user)
            await session.commit()
            await session.refresh(test_user)
        yield
        await engine.dispose()

    app = FastAPI(lifespan=lifespan)

    async def override_get_session() -> AsyncIterator[AsyncSession]:
        async with factory() as session:
            yield session

    async def override_get_current_user() -> User:
        async with factory() as session:
            from sqlalchemy import select

            return (await session.execute(select(User).where(User.id == test_user.id))).scalar_one()

    app.dependency_overrides[get_session] = override_get_session
    app.dependency_overrides[get_current_user] = override_get_current_user
    app.include_router(vocab_router)

    def run(coro_fn: Callable[[AsyncSession], object]) -> object:
        async def _runner() -> object:
            async with factory() as session:
                return await coro_fn(session)  # type: ignore[misc]

        return asyncio.run(_runner())

    with TestClient(app) as client:
        yield VocabFixture(client=client, user_id=test_user.id, run=run)


@pytest.fixture
def vocab_client(vocab_fixture: VocabFixture) -> TestClient:
    return vocab_fixture.client


def test_get_vocab_returns_empty_list_when_db_empty(vocab_client: TestClient) -> None:
    response = vocab_client.get("/vocab")
    assert response.status_code == 200
    assert response.json() == {"items": [], "page": 1, "page_size": 20, "total": 0}


def test_get_vocab_paginates_and_returns_total(vocab_fixture: VocabFixture) -> None:
    async def seed(session: AsyncSession) -> None:
        for i in range(25):
            session.add(VocabItem(token=f"word{i:02d}", language="en", definition=""))
        await session.commit()

    vocab_fixture.run(seed)

    response = vocab_fixture.client.get("/vocab", params={"page": 2, "page_size": 10})
    assert response.status_code == 200
    body = response.json()
    assert body["page"] == 2
    assert body["page_size"] == 10
    assert body["total"] == 25
    assert len(body["items"]) == 10


def test_post_vocab_creates_item_and_review_row_for_current_user(
    vocab_fixture: VocabFixture,
) -> None:
    response = vocab_fixture.client.post("/vocab", json={"token": "ephemeral", "language": "en"})
    assert response.status_code == 201
    body = response.json()
    assert body["token"] == "ephemeral"
    assert body["language"] == "en"
    assert body["definition"] == ""

    from sqlalchemy import select

    from app.models.review import Review

    async def assertions(session: AsyncSession) -> None:
        items = (await session.execute(select(VocabItem))).scalars().all()
        assert len(items) == 1
        assert items[0].token == "ephemeral"
        reviews = (
            (await session.execute(select(Review).where(Review.user_id == vocab_fixture.user_id)))
            .scalars()
            .all()
        )
        assert len(reviews) == 1
        assert reviews[0].vocab_item_id == items[0].id
        assert reviews[0].due_at is not None

    vocab_fixture.run(assertions)


def test_patch_vocab_suspend_toggles_review_suspended_flag(
    vocab_fixture: VocabFixture,
) -> None:
    from datetime import datetime

    from app.models.review import Review

    vocab_id_holder: dict[str, uuid.UUID] = {}

    async def seed(session: AsyncSession) -> None:
        item = VocabItem(token="lexical", language="en", definition="")
        session.add(item)
        await session.flush()
        vocab_id_holder["id"] = item.id
        session.add(
            Review(
                user_id=vocab_fixture.user_id,
                vocab_item_id=item.id,
                due_at=datetime.now(UTC),
                suspended=False,
            )
        )
        await session.commit()

    vocab_fixture.run(seed)
    vocab_id = vocab_id_holder["id"]

    first = vocab_fixture.client.patch(f"/vocab/{vocab_id}/suspend")
    assert first.status_code == 200
    assert first.json() == {"suspended": True}

    second = vocab_fixture.client.patch(f"/vocab/{vocab_id}/suspend")
    assert second.status_code == 200
    assert second.json() == {"suspended": False}


def test_patch_vocab_suspend_404_when_no_review_for_user(
    vocab_fixture: VocabFixture,
) -> None:
    vocab_id_holder: dict[str, uuid.UUID] = {}

    async def seed(session: AsyncSession) -> None:
        item = VocabItem(token="orphan", language="en", definition="")
        session.add(item)
        await session.flush()
        vocab_id_holder["id"] = item.id
        await session.commit()

    vocab_fixture.run(seed)

    response = vocab_fixture.client.patch(f"/vocab/{vocab_id_holder['id']}/suspend")
    assert response.status_code == 404


def test_delete_vocab_removes_item_and_cascades_reviews(
    vocab_fixture: VocabFixture,
) -> None:
    from datetime import datetime

    from sqlalchemy import select

    from app.models.review import Review

    vocab_id_holder: dict[str, uuid.UUID] = {}

    async def seed(session: AsyncSession) -> None:
        item = VocabItem(token="ephemeral", language="en", definition="")
        session.add(item)
        await session.flush()
        vocab_id_holder["id"] = item.id
        session.add(
            Review(
                user_id=vocab_fixture.user_id,
                vocab_item_id=item.id,
                due_at=datetime.now(UTC),
            )
        )
        await session.commit()

    vocab_fixture.run(seed)
    vocab_id = vocab_id_holder["id"]

    response = vocab_fixture.client.delete(f"/vocab/{vocab_id}")
    assert response.status_code == 204

    async def assertions(session: AsyncSession) -> None:
        items = (await session.execute(select(VocabItem))).scalars().all()
        assert len(items) == 0
        reviews = (await session.execute(select(Review))).scalars().all()
        assert len(reviews) == 0

    vocab_fixture.run(assertions)


def test_delete_vocab_404_when_item_missing(vocab_fixture: VocabFixture) -> None:
    response = vocab_fixture.client.delete(f"/vocab/{uuid.uuid4()}")
    assert response.status_code == 404


def test_post_vocab_rejects_empty_token(vocab_fixture: VocabFixture) -> None:
    response = vocab_fixture.client.post("/vocab", json={"token": "", "language": "en"})
    assert response.status_code == 422


def test_post_vocab_creates_review_for_existing_vocab_when_user_has_none(
    vocab_fixture: VocabFixture,
) -> None:
    async def seed(session: AsyncSession) -> None:
        session.add(VocabItem(token="serendipity", language="en", definition=""))
        await session.commit()

    vocab_fixture.run(seed)

    response = vocab_fixture.client.post("/vocab", json={"token": "serendipity", "language": "en"})
    assert response.status_code == 200

    from sqlalchemy import select

    from app.models.review import Review

    async def assertions(session: AsyncSession) -> None:
        reviews = (
            (await session.execute(select(Review).where(Review.user_id == vocab_fixture.user_id)))
            .scalars()
            .all()
        )
        assert len(reviews) == 1

    vocab_fixture.run(assertions)


def test_post_vocab_is_idempotent_on_token_language(vocab_fixture: VocabFixture) -> None:
    first = vocab_fixture.client.post("/vocab", json={"token": "ubiquitous", "language": "en"})
    assert first.status_code == 201
    first_id = first.json()["id"]

    second = vocab_fixture.client.post("/vocab", json={"token": "ubiquitous", "language": "en"})
    assert second.status_code == 200
    assert second.json()["id"] == first_id

    from sqlalchemy import select

    from app.models.review import Review

    async def assertions(session: AsyncSession) -> None:
        items = (await session.execute(select(VocabItem))).scalars().all()
        assert len(items) == 1
        reviews = (
            (await session.execute(select(Review).where(Review.user_id == vocab_fixture.user_id)))
            .scalars()
            .all()
        )
        assert len(reviews) == 1

    vocab_fixture.run(assertions)
