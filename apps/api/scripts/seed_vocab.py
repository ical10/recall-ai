"""Seed vocab from JSON or CSV."""

from __future__ import annotations

import argparse
import csv
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.core.db import SessionLocal
from app.models.review import Review
from app.models.user import User
from app.models.vocab_item import VocabItem


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Seed vocab items from JSON or CSV.")
    parser.add_argument("path", type=Path)
    parser.add_argument("--csv", action="store_true", help="Treat input as CSV")
    parser.add_argument(
        "--create-reviews-for",
        type=str,
        default=None,
        help="Email of user to create due Review rows for",
    )
    return parser.parse_args(argv)


def _read_rows(path: Path, *, csv_mode: bool) -> list[dict[str, str]]:
    text = path.read_text(encoding="utf-8")
    if csv_mode:
        return list(csv.DictReader(text.splitlines()))
    return list(json.loads(text))


async def main(session_factory: async_sessionmaker | None = None) -> None:
    args = _parse_args(sys.argv[1:])
    rows = _read_rows(args.path, csv_mode=args.csv)
    factory = session_factory or SessionLocal
    async with factory() as session:
        items: list[VocabItem] = []
        for row in rows:
            token = row["token"].strip()
            language = row["language"].strip()
            if not token or not language:
                continue
            existing = (
                await session.execute(
                    select(VocabItem).where(
                        VocabItem.token == token,
                        VocabItem.language == language,
                    )
                )
            ).scalar_one_or_none()
            if existing is not None:
                items.append(existing)
                continue
            item = VocabItem(token=token, language=language, definition="")
            session.add(item)
            await session.flush()
            items.append(item)

        if args.create_reviews_for:
            user = (
                await session.execute(select(User).where(User.email == args.create_reviews_for))
            ).scalar_one_or_none()
            if user is None:
                raise SystemExit(f"user with email {args.create_reviews_for!r} not found")
            now = datetime.now(UTC)
            for item in items:
                session.add(Review(user_id=user.id, vocab_item_id=item.id, due_at=now))

        await session.commit()


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
