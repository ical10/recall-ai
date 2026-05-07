from __future__ import annotations

import asyncio
import json
import sys
from collections.abc import Callable, Iterator
from datetime import UTC, datetime
from pathlib import Path

import pytest
from scripts.seed_vocab import main
from sqlalchemy import event, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.models import Base
from app.models.review import Review
from app.models.user import User
from app.models.vocab_item import VocabItem


@pytest.fixture
def session_factory(tmp_path: Path) -> Iterator[async_sessionmaker[AsyncSession]]:
    db_path = tmp_path / "test.db"
    engine = create_async_engine(f"sqlite+aiosqlite:///{db_path}", future=True)

    @event.listens_for(engine.sync_engine, "connect")
    def _enable_sqlite_fk(dbapi_connection: object, _conn_record: object) -> None:
        cursor = dbapi_connection.cursor()  # type: ignore[attr-defined]
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    async def _create_schema() -> None:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    asyncio.run(_create_schema())

    factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    yield factory
    asyncio.run(engine.dispose())


def _run(
    factory: async_sessionmaker[AsyncSession],
    coro_fn: Callable[[AsyncSession], object],
) -> object:
    async def _runner() -> object:
        async with factory() as session:
            return await coro_fn(session)  # type: ignore[misc]

    return asyncio.run(_runner())


def _invoke(
    factory: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
    argv: list[str],
) -> None:
    monkeypatch.setattr(sys, "argv", ["seed_vocab", *argv])
    asyncio.run(main(session_factory=factory))


def test_seed_vocab_inserts_rows_from_json(
    tmp_path: Path,
    session_factory: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seed_path = tmp_path / "seed.json"
    seed_path.write_text(
        json.dumps([{"token": "a", "language": "en"}, {"token": "b", "language": "en"}])
    )

    _invoke(session_factory, monkeypatch, [str(seed_path)])

    async def assertions(session: AsyncSession) -> None:
        items = (await session.execute(select(VocabItem))).scalars().all()
        assert {i.token for i in items} == {"a", "b"}

    _run(session_factory, assertions)


def test_seed_vocab_csv_format(
    tmp_path: Path,
    session_factory: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seed_path = tmp_path / "seed.csv"
    seed_path.write_text("token,language\nfoo,en\nbar,fr\n", encoding="utf-8")

    _invoke(session_factory, monkeypatch, [str(seed_path), "--csv"])

    async def assertions(session: AsyncSession) -> None:
        items = (await session.execute(select(VocabItem))).scalars().all()
        assert {(i.token, i.language) for i in items} == {("foo", "en"), ("bar", "fr")}

    _run(session_factory, assertions)


def test_seed_vocab_creates_due_reviews_when_flag_set(
    tmp_path: Path,
    session_factory: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def seed_user(session: AsyncSession) -> None:
        session.add(User(email="dev@local", google_id="dev-local", name="Dev"))
        await session.commit()

    _run(session_factory, seed_user)

    seed_path = tmp_path / "seed.json"
    seed_path.write_text(
        json.dumps([{"token": "x", "language": "en"}, {"token": "y", "language": "en"}])
    )

    _invoke(
        session_factory,
        monkeypatch,
        [str(seed_path), "--create-reviews-for", "dev@local"],
    )

    async def assertions(session: AsyncSession) -> None:
        reviews = (await session.execute(select(Review))).scalars().all()
        assert len(reviews) == 2
        now = datetime.now(UTC).replace(tzinfo=None)
        for r in reviews:
            assert r.due_at is not None
            due_naive = r.due_at.replace(tzinfo=None) if r.due_at.tzinfo else r.due_at
            assert due_naive <= now

    _run(session_factory, assertions)


def test_seed_vocab_prints_summary(
    tmp_path: Path,
    session_factory: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    seed_path = tmp_path / "seed.json"
    seed_path.write_text(
        json.dumps([{"token": "p", "language": "en"}, {"token": "q", "language": "en"}])
    )

    _invoke(session_factory, monkeypatch, [str(seed_path)])

    captured = capsys.readouterr()
    assert "seeded 2 vocab items" in captured.out
    assert "0 reviews" in captured.out


def test_seed_vocab_errors_when_json_is_not_a_list(
    tmp_path: Path,
    session_factory: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seed_path = tmp_path / "seed.json"
    seed_path.write_text(json.dumps({"token": "a", "language": "en"}))

    with pytest.raises(SystemExit):
        _invoke(session_factory, monkeypatch, [str(seed_path)])


def test_seed_vocab_skips_existing_reviews_on_rerun(
    tmp_path: Path,
    session_factory: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def seed_user(session: AsyncSession) -> None:
        session.add(User(email="dev@local", google_id="dev-local", name="Dev"))
        await session.commit()

    _run(session_factory, seed_user)

    seed_path = tmp_path / "seed.json"
    seed_path.write_text(json.dumps([{"token": "x", "language": "en"}]))

    _invoke(
        session_factory,
        monkeypatch,
        [str(seed_path), "--create-reviews-for", "dev@local"],
    )
    _invoke(
        session_factory,
        monkeypatch,
        [str(seed_path), "--create-reviews-for", "dev@local"],
    )

    async def assertions(session: AsyncSession) -> None:
        reviews = (await session.execute(select(Review))).scalars().all()
        assert len(reviews) == 1

    _run(session_factory, assertions)


def test_seed_vocab_errors_when_user_not_found(
    tmp_path: Path,
    session_factory: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seed_path = tmp_path / "seed.json"
    seed_path.write_text(json.dumps([{"token": "a", "language": "en"}]))

    with pytest.raises(SystemExit):
        _invoke(
            session_factory,
            monkeypatch,
            [str(seed_path), "--create-reviews-for", "missing@local"],
        )


def test_seed_vocab_skips_blank_rows(
    tmp_path: Path,
    session_factory: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seed_path = tmp_path / "seed.json"
    seed_path.write_text(
        json.dumps(
            [
                {"token": "", "language": "en"},
                {"token": "valid", "language": "en"},
                {"token": "ws", "language": "  "},
            ]
        )
    )

    _invoke(session_factory, monkeypatch, [str(seed_path)])

    async def assertions(session: AsyncSession) -> None:
        items = (await session.execute(select(VocabItem))).scalars().all()
        assert {i.token for i in items} == {"valid"}

    _run(session_factory, assertions)


def test_seed_vocab_skips_duplicates(
    tmp_path: Path,
    session_factory: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def seed(session: AsyncSession) -> None:
        session.add(VocabItem(token="a", language="en", definition=""))
        await session.commit()

    _run(session_factory, seed)

    seed_path = tmp_path / "seed.json"
    seed_path.write_text(
        json.dumps([{"token": "a", "language": "en"}, {"token": "c", "language": "en"}])
    )

    _invoke(session_factory, monkeypatch, [str(seed_path)])

    async def assertions(session: AsyncSession) -> None:
        items = (await session.execute(select(VocabItem))).scalars().all()
        assert {i.token for i in items} == {"a", "c"}

    _run(session_factory, assertions)
