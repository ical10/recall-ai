"""Seed Vocab Items from JSON or CSV.

Usage:
  python -m scripts.seed_vocab path/to/seed.json
  python -m scripts.seed_vocab path/to/seed.csv --csv
  python -m scripts.seed_vocab seed.json --create-reviews-for dev@local
  python -m scripts.seed_vocab seed.json --create-reviews-for dev@local --ensure-user \
      --user-name Dev --user-timezone UTC
"""

from __future__ import annotations

import argparse
import asyncio
import csv
import json
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import SessionLocal
from app.models.review import Review
from app.models.user import User
from app.models.vocab_item import VocabItem


def _read_rows(path: Path, *, csv_mode: bool) -> list[dict[str, str]]:
    text = path.read_text(encoding="utf-8")
    if csv_mode:
        return list(csv.DictReader(text.splitlines()))
    data = json.loads(text)
    if not isinstance(data, list):
        raise SystemExit("seed JSON must be a list of {token, language} objects")
    return data


async def _upsert_vocab(session: AsyncSession, rows: list[dict[str, str]]) -> list[VocabItem]:
    items: list[VocabItem] = []
    for row in rows:
        token = row.get("token", "").strip()
        language = row.get("language", "").strip()
        if not token or not language:
            continue
        existing = (
            await session.execute(
                select(VocabItem).where(VocabItem.token == token, VocabItem.language == language)
            )
        ).scalar_one_or_none()
        if existing:
            items.append(existing)
            continue
        item = VocabItem(token=token, language=language, definition="")
        session.add(item)
        await session.flush()
        items.append(item)
    return items


async def _upsert_user(
    session: AsyncSession,
    email: str,
    name: str,
    tz: str,  # noqa: ARG001
) -> User:
    """Get-or-create a User by email; idempotent.

    Used only when --ensure-user is passed — a dev-environment convenience so a
    fresh DB does not need an HTTP request pre-step to create the dev user.

    Note: tz is accepted for forward compatibility with Slice C (which adds
    User.timezone). It is not persisted until that migration lands.
    """
    user = (await session.execute(select(User).where(User.email == email))).scalar_one_or_none()
    if user is not None:
        return user
    user = User(
        email=email,
        google_id=f"seed-{email}",
        name=name,
    )
    session.add(user)
    await session.flush()
    return user


async def _ensure_reviews(session: AsyncSession, items: list[VocabItem], email: str) -> int:
    user = (await session.execute(select(User).where(User.email == email))).scalar_one_or_none()
    if user is None:
        raise SystemExit(
            f"user with email {email!r} not found — "
            f"run the app once to create {email}, or re-run with --ensure-user"
        )
    created = 0
    now = datetime.now(UTC)
    for item in items:
        existing = (
            await session.execute(
                select(Review).where(Review.user_id == user.id, Review.vocab_item_id == item.id)
            )
        ).scalar_one_or_none()
        if existing:
            continue
        session.add(Review(user_id=user.id, vocab_item_id=item.id, due_at=now))
        created += 1
    return created


async def main(
    session_factory: Callable[[], AsyncSession] | None = None,
) -> None:
    parser = argparse.ArgumentParser(description="Seed Vocab Items from JSON or CSV.")
    parser.add_argument("path", type=Path)
    parser.add_argument("--csv", action="store_true", help="Treat input as CSV")
    parser.add_argument(
        "--create-reviews-for",
        type=str,
        default=None,
        help="Email of user to create due Review rows for",
    )
    parser.add_argument(
        "--ensure-user",
        action="store_true",
        help="Upsert the --create-reviews-for user if missing (dev convenience)",
    )
    parser.add_argument(
        "--user-name",
        type=str,
        default="Dev",
        help="Name to use when --ensure-user creates a new row",
    )
    parser.add_argument(
        "--user-timezone",
        type=str,
        default="UTC",
        help="IANA timezone for --ensure-user (stored when Slice C migration lands)",
    )
    args = parser.parse_args()

    if args.ensure_user and not args.create_reviews_for:
        parser.error("--ensure-user requires --create-reviews-for")

    rows = _read_rows(args.path, csv_mode=args.csv)
    factory = session_factory or SessionLocal
    async with factory() as session:
        items = await _upsert_vocab(session, rows)
        review_count = 0
        if args.create_reviews_for:
            if args.ensure_user:
                await _upsert_user(
                    session,
                    email=args.create_reviews_for,
                    name=args.user_name,
                    tz=args.user_timezone,
                )
            review_count = await _ensure_reviews(session, items, args.create_reviews_for)
        await session.commit()
    print(f"seeded {len(items)} vocab items; created {review_count} reviews")


if __name__ == "__main__":
    asyncio.run(main())
