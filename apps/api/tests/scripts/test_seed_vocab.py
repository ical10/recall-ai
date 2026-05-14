"""Tests for scripts.seed_vocab CLI.

The seed script is tested by calling main() directly with a monkeypatched
sys.argv and an injected session_factory pointed at a SQLite test DB.
"""

from __future__ import annotations

import asyncio
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.models import Base
from app.models.review import Review
from app.models.user import User
from app.models.vocab_item import VocabItem

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_factory(db_path: str) -> async_sessionmaker[AsyncSession]:
    engine = create_async_engine(f"sqlite+aiosqlite:///{db_path}", future=True)

    async def _create_schema() -> None:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    asyncio.run(_create_schema())
    return async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


def _run_seed(argv: list[str], factory: async_sessionmaker[AsyncSession]) -> str:
    """Patch sys.argv and call main() with an injected factory; return printed output."""
    import io
    from contextlib import redirect_stdout

    from scripts.seed_vocab import main

    sys.argv = ["seed_vocab"] + argv
    buf = io.StringIO()
    with redirect_stdout(buf):
        asyncio.run(main(session_factory=factory))
    return buf.getvalue().strip()


async def _count_vocab(factory: async_sessionmaker[AsyncSession]) -> int:
    async with factory() as s:
        return int((await s.execute(select(func.count(VocabItem.id)))).scalar_one())


async def _count_reviews(factory: async_sessionmaker[AsyncSession]) -> int:
    async with factory() as s:
        return int((await s.execute(select(func.count(Review.id)))).scalar_one())


async def _count_users(factory: async_sessionmaker[AsyncSession]) -> int:
    async with factory() as s:
        return int((await s.execute(select(func.count(User.id)))).scalar_one())


async def _seed_user(
    factory: async_sessionmaker[AsyncSession], email: str, name: str = "Dev"
) -> User:
    async with factory() as s:
        u = User(email=email, google_id=f"gid-{email}", name=name)
        s.add(u)
        await s.commit()
        await s.refresh(u)
        return u


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_seed_vocab_inserts_rows_from_json(tmp_path: Path) -> None:
    factory = _make_factory(str(tmp_path / "db.sqlite"))
    seed_file = tmp_path / "seed.json"
    seed_file.write_text(
        json.dumps([{"token": "alpha", "language": "en"}, {"token": "beta", "language": "en"}])
    )
    out = _run_seed([str(seed_file)], factory)
    assert asyncio.run(_count_vocab(factory)) == 2
    assert "seeded 2 vocab items" in out


def test_seed_vocab_skips_duplicates(tmp_path: Path) -> None:
    factory = _make_factory(str(tmp_path / "db.sqlite"))

    async def pre_insert() -> None:
        async with factory() as s:
            s.add(VocabItem(token="alpha", language="en", definition=""))
            await s.commit()

    asyncio.run(pre_insert())

    seed_file = tmp_path / "seed.json"
    seed_file.write_text(
        json.dumps([{"token": "alpha", "language": "en"}, {"token": "gamma", "language": "en"}])
    )
    _run_seed([str(seed_file)], factory)
    assert asyncio.run(_count_vocab(factory)) == 2


def test_seed_vocab_csv_format(tmp_path: Path) -> None:
    factory = _make_factory(str(tmp_path / "db.sqlite"))
    seed_file = tmp_path / "seed.csv"
    seed_file.write_text("token,language\nfoo,en\nbar,fr\n")
    out = _run_seed([str(seed_file), "--csv"], factory)
    assert asyncio.run(_count_vocab(factory)) == 2
    assert "seeded 2 vocab items" in out


def test_seed_vocab_creates_due_reviews_when_flag_set(tmp_path: Path) -> None:
    factory = _make_factory(str(tmp_path / "db.sqlite"))
    asyncio.run(_seed_user(factory, "dev@local"))
    seed_file = tmp_path / "seed.json"
    seed_file.write_text(
        json.dumps([{"token": "zap", "language": "en"}, {"token": "zip", "language": "en"}])
    )
    _run_seed([str(seed_file), "--create-reviews-for", "dev@local"], factory)
    assert asyncio.run(_count_reviews(factory)) == 2


def test_seed_vocab_due_reviews_have_past_or_present_due_at(tmp_path: Path) -> None:
    factory = _make_factory(str(tmp_path / "db.sqlite"))
    asyncio.run(_seed_user(factory, "dev@local"))
    seed_file = tmp_path / "seed.json"
    seed_file.write_text(json.dumps([{"token": "now_word", "language": "en"}]))
    _run_seed([str(seed_file), "--create-reviews-for", "dev@local"], factory)

    async def check_due() -> bool:
        async with factory() as s:
            rv = (await s.execute(select(Review))).scalar_one()
            if rv.due_at is None:
                return False
            # SQLite returns naive datetimes; normalise before comparing.
            due = rv.due_at
            if due.tzinfo is None:
                due = due.replace(tzinfo=UTC)
            return due <= datetime.now(UTC)

    assert asyncio.run(check_due())


def test_seed_vocab_skips_blank_token_rows(tmp_path: Path) -> None:
    factory = _make_factory(str(tmp_path / "db.sqlite"))
    seed_file = tmp_path / "seed.json"
    seed_file.write_text(json.dumps([{"token": "", "language": "en"}]))
    _run_seed([str(seed_file)], factory)
    assert asyncio.run(_count_vocab(factory)) == 0


def test_seed_vocab_errors_when_user_not_found(tmp_path: Path) -> None:
    factory = _make_factory(str(tmp_path / "db.sqlite"))
    seed_file = tmp_path / "seed.json"
    seed_file.write_text(json.dumps([{"token": "x", "language": "en"}]))
    with pytest.raises(SystemExit):
        _run_seed([str(seed_file), "--create-reviews-for", "missing@local"], factory)


def test_seed_vocab_ensure_user_upserts_missing_user(tmp_path: Path) -> None:
    factory = _make_factory(str(tmp_path / "db.sqlite"))
    seed_file = tmp_path / "seed.json"
    seed_file.write_text(json.dumps([{"token": "newword", "language": "en"}]))
    _run_seed(
        [
            str(seed_file),
            "--create-reviews-for",
            "dev@local",
            "--ensure-user",
            "--user-name",
            "Dev",
            "--user-timezone",
            "Asia/Jakarta",
        ],
        factory,
    )
    assert asyncio.run(_count_users(factory)) == 1
    assert asyncio.run(_count_reviews(factory)) == 1

    async def check_timezone() -> str | None:
        async with factory() as s:
            user = (await s.execute(select(User))).scalar_one_or_none()
            return user.timezone if user else None

    assert asyncio.run(check_timezone()) == "Asia/Jakarta"


def test_seed_vocab_ensure_user_is_idempotent(tmp_path: Path) -> None:
    factory = _make_factory(str(tmp_path / "db.sqlite"))
    asyncio.run(_seed_user(factory, "dev@local"))
    seed_file = tmp_path / "seed.json"
    seed_file.write_text(json.dumps([{"token": "dup", "language": "en"}]))
    _run_seed(
        [str(seed_file), "--create-reviews-for", "dev@local", "--ensure-user"],
        factory,
    )
    assert asyncio.run(_count_users(factory)) == 1
    assert asyncio.run(_count_reviews(factory)) == 1


def test_seed_vocab_ensure_user_without_create_reviews_for_errors(tmp_path: Path) -> None:
    factory = _make_factory(str(tmp_path / "db.sqlite"))
    seed_file = tmp_path / "seed.json"
    seed_file.write_text(json.dumps([{"token": "x", "language": "en"}]))
    with pytest.raises(SystemExit):
        _run_seed([str(seed_file), "--ensure-user"], factory)


def test_seed_vocab_skips_blank_language_rows(tmp_path: Path) -> None:
    factory = _make_factory(str(tmp_path / "db.sqlite"))
    seed_file = tmp_path / "seed.json"
    seed_file.write_text(json.dumps([{"token": "hello", "language": ""}]))
    _run_seed([str(seed_file)], factory)
    assert asyncio.run(_count_vocab(factory)) == 0
