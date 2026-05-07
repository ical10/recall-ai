# Slice D — Vocab CRUD + admin seed script

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Endpoints to list / create / suspend / delete vocab items, plus a CLI seed script to bootstrap a deck from a JSON or CSV file. Creating a vocab item also creates a `Review` row for the current user with `due_at = now()` so it shows up immediately in `/review`. The seed script is the practical entry point for filling the daily content-generation pipeline (Slice A) with targets to enrich.

**Architecture:** A single `app/api/vocab.py` sub-router with four endpoints. JSON-only for v1 — no HTMX list page in this slice (a follow-up can add `pages/vocab.html`). Idempotent `POST /vocab` keys on the `(token, language)` unique constraint and returns 200 on existing or 201 on create. The seed script runs against the async DB engine via `asyncio.run`, so it has no dependency on Slice A's `db_sync` module.

**Prerequisite:** Slice 0 merged (provides `get_current_user`, `app.api.router`).

**Tech stack:** FastAPI async, SQLAlchemy 2.0 async, pydantic v2, Python `argparse` for the seed CLI.

---

## File Structure

**Create:**
- `apps/api/app/schemas/vocab.py` — `VocabCreate`, `VocabRead`, `VocabListResponse`
- `apps/api/app/api/vocab.py` — sub-router with the four endpoints
- `apps/api/scripts/__init__.py`
- `apps/api/scripts/seed_vocab.py` — CLI seed entrypoint
- `apps/api/scripts/seed_examples.json` — small example seed file (3-5 rows) for smoke testing
- `apps/api/tests/api/test_vocab.py`
- `apps/api/tests/scripts/__init__.py`
- `apps/api/tests/scripts/test_seed_vocab.py`

**Modify:**
- `apps/api/app/api/router.py` — add `router.include_router(vocab_router)`

**No edits to:** any model, migration, existing schema, `main.py`, `base.html`.

---

## Task 1: Schemas

- [ ] **Step 1**: Create `apps/api/app/schemas/vocab.py`:

```python
from __future__ import annotations

from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field


class VocabCreate(BaseModel):
    token: str = Field(min_length=1, max_length=255)
    language: str = Field(min_length=2, max_length=35)


class VocabRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    token: str
    language: str
    part_of_speech: str | None = None
    definition: str
    example_sentence: str | None = None


class VocabListResponse(BaseModel):
    items: list[VocabRead]
    page: int = Field(ge=1)
    page_size: int = Field(ge=1, le=100)
    total: int = Field(ge=0)
```

- [ ] **Step 2**: Commit — `feat: add Vocab schemas`.

---

## Task 2: Sub-router with the four endpoints

- [ ] **Step 1**: Create `apps/api/app/api/vocab.py`:

```python
from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.db import get_session
from app.models.review import Review
from app.models.user import User
from app.models.vocab_item import VocabItem
from app.schemas.vocab import VocabCreate, VocabListResponse, VocabRead

router = APIRouter()


@router.get("/vocab", response_model=VocabListResponse)
async def list_vocab(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    session: AsyncSession = Depends(get_session),
) -> VocabListResponse:
    total = (await session.execute(select(func.count(VocabItem.id)))).scalar_one()
    rows = (await session.execute(
        select(VocabItem)
        .order_by(VocabItem.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )).scalars().all()
    return VocabListResponse(
        items=[VocabRead.model_validate(r) for r in rows],
        page=page, page_size=page_size, total=int(total),
    )


@router.post("/vocab", status_code=201)
async def create_vocab(
    body: VocabCreate,
    response: Response,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
) -> VocabRead:
    existing = (await session.execute(
        select(VocabItem).where(
            VocabItem.token == body.token, VocabItem.language == body.language,
        )
    )).scalar_one_or_none()
    if existing is not None:
        item = existing
        response.status_code = 200
    else:
        item = VocabItem(token=body.token, language=body.language, definition="")
        session.add(item)
        await session.flush()
    review = (await session.execute(
        select(Review).where(
            Review.user_id == user.id, Review.vocab_item_id == item.id,
        )
    )).scalar_one_or_none()
    if review is None:
        session.add(Review(
            user_id=user.id,
            vocab_item_id=item.id,
            due_at=datetime.now(timezone.utc),
        ))
    await session.commit()
    await session.refresh(item)
    return VocabRead.model_validate(item)


@router.patch("/vocab/{vocab_id}/suspend")
async def suspend_vocab(
    vocab_id: UUID,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
) -> dict[str, bool]:
    review = (await session.execute(
        select(Review).where(
            Review.user_id == user.id, Review.vocab_item_id == vocab_id,
        )
    )).scalar_one_or_none()
    if review is None:
        raise HTTPException(status_code=404)
    review.suspended = not review.suspended
    await session.commit()
    return {"suspended": review.suspended}


@router.delete("/vocab/{vocab_id}", status_code=204)
async def delete_vocab(
    vocab_id: UUID,
    session: AsyncSession = Depends(get_session),
    _user: User = Depends(get_current_user),
) -> None:
    result = await session.execute(
        delete(VocabItem).where(VocabItem.id == vocab_id)
    )
    if result.rowcount == 0:
        raise HTTPException(status_code=404)
    await session.commit()
```

`POST` body validates min/max lengths via the schema. Idempotency: if `(token, language)` exists, return the existing row with status 200; otherwise insert with 201. Either way, ensure a `Review` row exists for `current_user` with `due_at=now()`. `definition=""` is the marker the Slice A selection service keys off.

- [ ] **Step 2**: Commit — `feat: add vocab CRUD endpoints (list/create/suspend/delete)`.

---

## Task 3: Wire the router

- [ ] **Step 1**: Edit `apps/api/app/api/router.py` — append the vocab include after dashboard and reviews:

```python
from fastapi import APIRouter

from app.api.dashboard import router as dashboard_router
from app.api.reviews import router as reviews_router
from app.api.vocab import router as vocab_router

router = APIRouter()
router.include_router(dashboard_router)
router.include_router(reviews_router)
router.include_router(vocab_router)
```

If you are merging Slice D before some of A/B/C, only include the routers that exist in `main`. The squash-merge of subsequent slices will append additional includes — trivial three-way merge.

- [ ] **Step 2**: Commit — `feat: wire vocab router into app.api.router`.

---

## Task 4: Seed script

- [ ] **Step 1**: Create `apps/api/scripts/__init__.py` (empty).

- [ ] **Step 2**: Create `apps/api/scripts/seed_vocab.py`:

```python
"""Seed vocab from JSON or CSV.

Usage:
  python -m scripts.seed_vocab path/to/seed.json
  python -m scripts.seed_vocab path/to/seed.csv --csv
  python -m scripts.seed_vocab seed.json --create-reviews-for dev@local
"""
from __future__ import annotations

import argparse
import asyncio
import csv
import json
from datetime import datetime, timezone
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
        return [row for row in csv.DictReader(text.splitlines())]
    data = json.loads(text)
    if not isinstance(data, list):
        raise SystemExit("seed JSON must be a list of {token, language} objects")
    return data


async def _upsert_vocab(session: AsyncSession, rows: list[dict[str, str]]) -> list[VocabItem]:
    items: list[VocabItem] = []
    for row in rows:
        token = row["token"].strip()
        language = row["language"].strip()
        if not token or not language:
            continue
        existing = (await session.execute(
            select(VocabItem).where(
                VocabItem.token == token, VocabItem.language == language,
            )
        )).scalar_one_or_none()
        if existing:
            items.append(existing)
            continue
        item = VocabItem(token=token, language=language, definition="")
        session.add(item)
        await session.flush()
        items.append(item)
    return items


async def _ensure_reviews(session: AsyncSession, items: list[VocabItem], email: str) -> int:
    user = (await session.execute(
        select(User).where(User.email == email)
    )).scalar_one_or_none()
    if user is None:
        raise SystemExit(f"user with email {email!r} not found — run the app once to create dev@local")
    created = 0
    now = datetime.now(timezone.utc)
    for item in items:
        existing = (await session.execute(
            select(Review).where(
                Review.user_id == user.id, Review.vocab_item_id == item.id,
            )
        )).scalar_one_or_none()
        if existing:
            continue
        session.add(Review(user_id=user.id, vocab_item_id=item.id, due_at=now))
        created += 1
    return created


async def main() -> None:
    parser = argparse.ArgumentParser(description="Seed vocab items from JSON or CSV.")
    parser.add_argument("path", type=Path)
    parser.add_argument("--csv", action="store_true", help="Treat input as CSV")
    parser.add_argument("--create-reviews-for", type=str, default=None,
                        help="Email of user to create due Review rows for")
    args = parser.parse_args()

    rows = _read_rows(args.path, csv_mode=args.csv)
    async with SessionLocal() as session:
        items = await _upsert_vocab(session, rows)
        review_count = 0
        if args.create_reviews_for:
            review_count = await _ensure_reviews(session, items, args.create_reviews_for)
        await session.commit()
    print(f"seeded {len(items)} vocab items; created {review_count} reviews")


if __name__ == "__main__":
    asyncio.run(main())
```

- [ ] **Step 3**: Create `apps/api/scripts/seed_examples.json`:

```json
[
  {"token": "ephemeral", "language": "en"},
  {"token": "ubiquitous", "language": "en"},
  {"token": "serendipity", "language": "en"},
  {"token": "Schadenfreude", "language": "de"}
]
```

- [ ] **Step 4**: Commit — `feat: add seed_vocab CLI script and example seed file`.

---

## Task 5: Tests

- [ ] **Step 1**: Create `apps/api/tests/api/test_vocab.py` with:

```python
def test_get_vocab_paginates_and_returns_total(...):
    # Insert 25 VocabItems; GET /vocab?page=2&page_size=10 → 10 items, total=25, page=2.

def test_post_vocab_creates_item_and_review_row_for_current_user(...):
    # POST {token:"new", language:"en"} → 201; assert VocabItem and Review (user_id=current_user.id) exist.

def test_post_vocab_is_idempotent_on_token_language(...):
    # POST same body twice. First → 201, second → 200. Only one VocabItem; only one Review.

def test_post_vocab_creates_review_for_existing_vocab_when_user_has_none(...):
    # Pre-insert VocabItem without a Review for current_user; POST same token/language → 200,
    # assert a Review row was created.

def test_patch_vocab_suspend_toggles_review_suspended_flag(...):
    # Pre-insert Review with suspended=False; PATCH → {"suspended": true}; PATCH again → {"suspended": false}.

def test_patch_vocab_suspend_404_when_no_review_for_user(...):
    # Pre-insert VocabItem but no Review for current_user; PATCH → 404.

def test_delete_vocab_removes_item_and_cascades_reviews(...):
    # Pre-insert VocabItem + Review for current_user. DELETE → 204; both rows gone.

def test_delete_vocab_404_when_item_missing(...): ...

def test_post_vocab_rejects_empty_token(...):
    # body {"token": "", "language": "en"} → 422.
```

- [ ] **Step 2**: Create `apps/api/tests/scripts/__init__.py` (empty) and `apps/api/tests/scripts/test_seed_vocab.py`:

```python
def test_seed_vocab_inserts_rows_from_json(tmp_path, ...):
    # Write [{"token":"a","language":"en"}, {"token":"b","language":"en"}] to tmp_path/seed.json;
    # invoke via subprocess or by calling main() with sys.argv patched. Assert 2 VocabItems exist.

def test_seed_vocab_skips_duplicates(...):
    # Pre-insert one row. Run seed with the same row + a new one → 2 items total, not 3.

def test_seed_vocab_csv_format(tmp_path, ...):
    # Write CSV with header "token,language\nfoo,en\n"; --csv flag; assert insertion.

def test_seed_vocab_creates_due_reviews_when_flag_set(tmp_path, ...):
    # Pre-create dev@local user; run with --create-reviews-for dev@local; assert Review rows
    # exist for both seeded items with due_at <= now.

def test_seed_vocab_skips_blank_rows(...):
    # JSON contains {"token":"","language":"en"} → skipped, no VocabItem inserted for that row.

def test_seed_vocab_errors_when_user_not_found(...):
    # No user; --create-reviews-for missing@local → SystemExit.
```

The simplest invocation in tests is to import `scripts.seed_vocab` and call its `main()` while monkeypatching `sys.argv`. To avoid clobbering the test session, override `app.core.db.SessionLocal` to point at the test session — or have `main()` accept an injected sessionmaker (cleaner; recommended). Refactor `main()` to take an optional `session_factory` parameter so tests can pass the test sessionmaker without monkeypatching:

```python
async def main(session_factory=None) -> None:
    ...
    async with (session_factory or SessionLocal)() as session:
        ...
```

- [ ] **Step 3**: Commit — `test: cover vocab CRUD endpoints and seed script`.

---

## Task 6: Verification + PR

- [ ] **Step 1**: Tests:
```
uv run pytest apps/api/tests/api/test_vocab.py apps/api/tests/scripts/test_seed_vocab.py -v
```

- [ ] **Step 2**: Lint:
```
pnpm lint
```

- [ ] **Step 3**: End-to-end smoke (requires Postgres up + dev user existing — start the app once, hit any endpoint to create `dev@local`):
```
pnpm dev
# in another terminal:
curl -s -X POST http://localhost:8000/vocab \
  -H 'content-type: application/json' \
  -d '{"token":"ephemeral","language":"en"}'

uv run --project . python -m scripts.seed_vocab apps/api/scripts/seed_examples.json --create-reviews-for dev@local
# expected output: "seeded 4 vocab items; created N reviews"

curl -s 'http://localhost:8000/vocab?page=1&page_size=20'
open http://localhost:8000/review     # the seeded items should appear in turn
```

- [ ] **Step 4**: Open PR titled `feat: vocab CRUD + seed script (Slice D)`. Squash-merge after review.

---

## Acceptance criteria

- `GET /vocab` returns paginated items + correct total.
- `POST /vocab` creates a VocabItem (status 201) and a due Review row for `current_user`. Repeated POST with the same `(token, language)` returns 200 with the existing row, no duplicate Review for the same user.
- `PATCH /vocab/{id}/suspend` toggles `Review.suspended` for the (current_user, vocab_id) pair; 404 when no Review exists for that user.
- `DELETE /vocab/{id}` removes the VocabItem and cascades to Reviews; 204 on success, 404 if missing.
- `python -m scripts.seed_vocab path.json` upserts rows and skips duplicates. With `--create-reviews-for <email>`, creates due Review rows for that user.
- Invalid input (empty token, oversized strings) → 422.
- All tests in `tests/api/test_vocab.py` and `tests/scripts/test_seed_vocab.py` pass; ruff + mypy clean.

## Notes / gotchas

- **`definition=""` placeholder.** This is the convention Slice A's `select_unenriched` keys off. Do not use `NULL` or some other sentinel. `nullable=False` on the column (see `apps/api/app/models/vocab_item.py:17`) precludes `NULL` anyway.
- **Idempotency on `POST`.** The unique constraint `uq_vocab_items_token_language` (see `apps/api/app/models/vocab_item.py:11`) is the source of truth. Catching the `IntegrityError` on a race-conditioned insert and falling back to a SELECT is safer than the current "select-then-insert" — wrap the insert in a try/except `IntegrityError` if you expect concurrent POSTs. For v1 (single-user dev), the simple flow is fine.
- **CASCADE delete.** `Review.user_id` and `Review.vocab_item_id` both have `ondelete="CASCADE"` (see `apps/api/app/models/review.py:26,29`). Deleting a VocabItem automatically deletes its reviews — no application-side cleanup needed.
- **No HTML page in this slice.** `GET /vocab` returns JSON only. A future slice can add `pages/vocab.html` with an HTMX list table using these endpoints.
- **Auth replacement seam.** All four routes use `get_current_user`. When real auth lands, no changes are needed here.
- **Seed script imports.** Run from `apps/api/` so `scripts.seed_vocab` resolves on the python path. Or use `uv run --project . python apps/api/scripts/seed_vocab.py` from the repo root — both work.
