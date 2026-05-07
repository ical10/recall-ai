# Slice B — Review session UI (HTMX)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Server-rendered HTMX flow for a review session: pick the oldest due card for the current user → reveal the definition → rate quality (Again / Hard / Good / Easy) → SM-2 update + persistence → next card or "done" state. Entirely server-driven; no custom JavaScript beyond HTMX attributes.

**Architecture:** A single `app/api/reviews.py` sub-router exposing three endpoints — `GET /review` (full page on initial load), `GET /review/{id}/reveal` (HTMX partial showing definition + rating buttons), `POST /review/{id}/rate` (form-encoded quality, runs SM-2, returns next-card partial or done partial). HTMX swaps the `#review-card` element via `hx-target="this" hx-swap="outerHTML"`. SM-2 is the existing pure function `compute_next_review`; this slice only handles persistence (writing back `ease_factor`, `interval_days`, `repetitions`, `last_reviewed_at`, `due_at`).

**Prerequisite:** Slice 0 merged (provides `get_current_user` + `templates` + `app.api.router`).

**Tech stack:** FastAPI async, SQLAlchemy 2.0 async (`get_session`), Jinja2, HTMX 2.0.4 (already on `base.html`), Tailwind compiled output. Uses `app/services/sm2.py:compute_next_review`, `app/schemas/review.py:ReviewState/ReviewUpdate/ReviewQuality`, `app/models/review.py:Review`, `app/models/vocab_item.py:VocabItem`.

---

## File Structure

**Create:**
- `apps/api/app/api/reviews.py` — sub-router with the three endpoints
- `apps/api/templates/pages/review.html` — full-page wrapper extending `base.html`
- `apps/api/templates/partials/card.html` — token + reveal button
- `apps/api/templates/partials/rating.html` — definition + 4 rating buttons
- `apps/api/templates/partials/done.html` — empty-state when no due reviews
- `apps/api/tests/api/test_reviews.py`

**Modify:**
- `apps/api/app/api/router.py` — add `router.include_router(reviews_router)`

**No edits to:** any model, schema (other than imports), service, migration, `main.py`, base template.

---

## Task 1: Sub-router + due-card query helper

- [ ] **Step 1**: Create `apps/api/app/api/reviews.py` with the route skeleton:

```python
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import Response
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.api.deps import get_current_user, templates
from app.core.db import get_session
from app.models.review import Review, ReviewQuality
from app.models.user import User
from app.models.vocab_item import VocabItem
from app.schemas.review import ReviewState
from app.services.sm2 import compute_next_review

router = APIRouter()


async def _next_due_review(
    session: AsyncSession, user_id: UUID, now: datetime
) -> Review | None:
    stmt = (
        select(Review)
        .options(joinedload(Review.vocab_item))   # see step 2
        .where(
            Review.user_id == user_id,
            Review.suspended.is_(False),
            or_(Review.due_at.is_(None), Review.due_at <= now),
        )
        .order_by(Review.due_at.asc().nulls_first(), Review.created_at.asc())
        .limit(1)
    )
    return (await session.execute(stmt)).scalar_one_or_none()
```

- [ ] **Step 2**: `joinedload(Review.vocab_item)` requires `Review` to declare a relationship to `VocabItem`. Check `apps/api/app/models/review.py` — if there is no `vocab_item: Mapped["VocabItem"] = relationship(...)` field yet, add one in this slice. (This is a non-schema change — relationships are ORM-only and don't generate a migration.) Add to `apps/api/app/models/review.py`:

```python
from sqlalchemy.orm import relationship
# inside class Review:
vocab_item: Mapped["VocabItem"] = relationship("VocabItem", lazy="raise")
```

`lazy="raise"` makes accidental N+1 lazy loads explicit. The query above eagerly loads via `joinedload`. Add the matching back-population on `VocabItem` only if you need it elsewhere — not required here.

- [ ] **Step 3**: Commit — `feat: add reviews router skeleton and Review.vocab_item relationship`.

---

## Task 2: `GET /review` — full page

- [ ] **Step 1**: Append to `apps/api/app/api/reviews.py`:

```python
@router.get("/review")
async def review_page(
    request: Request,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
) -> Response:
    now = datetime.now(timezone.utc)
    review = await _next_due_review(session, user.id, now)
    if review is None:
        return templates.TemplateResponse(request, "partials/done.html")
    return templates.TemplateResponse(
        request,
        "pages/review.html",
        {"review": review, "vocab": review.vocab_item},
    )
```

- [ ] **Step 2**: Create `apps/api/templates/pages/review.html`:

```html
{% extends "base.html" %}
{% block title %}Review — RecallAI{% endblock %}
{% block content %}
<main class="max-w-xl mx-auto px-4 py-12">
  {% include "partials/card.html" %}
</main>
{% endblock %}
```

- [ ] **Step 3**: Create `apps/api/templates/partials/card.html`:

```html
<div id="review-card" class="rounded-lg border border-slate-200 bg-white p-8 shadow-sm" hx-target="this" hx-swap="outerHTML">
  <p class="text-sm uppercase tracking-wide text-slate-500">{{ vocab.language }}</p>
  <h1 class="mt-2 text-3xl font-semibold text-slate-900">{{ vocab.token }}</h1>
  <button
    class="mt-6 rounded-md bg-slate-900 px-4 py-2 text-white hover:bg-slate-700"
    hx-get="/review/{{ review.id }}/reveal">
    Reveal definition
  </button>
</div>
```

- [ ] **Step 4**: Create `apps/api/templates/partials/done.html`:

```html
<div id="review-card" class="rounded-lg border border-slate-200 bg-white p-8 text-center shadow-sm">
  <h1 class="text-2xl font-semibold text-slate-900">All caught up</h1>
  <p class="mt-2 text-slate-600">No reviews due right now.</p>
  <a class="mt-6 inline-block rounded-md bg-slate-900 px-4 py-2 text-white" href="/dashboard">Go to dashboard</a>
</div>
```

- [ ] **Step 5**: Commit — `feat: add GET /review and review page templates`.

---

## Task 3: `GET /review/{id}/reveal` — HTMX partial

- [ ] **Step 1**: Append:

```python
@router.get("/review/{review_id}/reveal")
async def review_reveal(
    review_id: UUID,
    request: Request,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
) -> Response:
    stmt = (
        select(Review)
        .options(joinedload(Review.vocab_item))
        .where(Review.id == review_id, Review.user_id == user.id)
    )
    review = (await session.execute(stmt)).scalar_one_or_none()
    if review is None:
        raise HTTPException(status_code=404)
    return templates.TemplateResponse(
        request,
        "partials/rating.html",
        {"review": review, "vocab": review.vocab_item},
    )
```

- [ ] **Step 2**: Create `apps/api/templates/partials/rating.html`:

```html
<div id="review-card" class="rounded-lg border border-slate-200 bg-white p-8 shadow-sm" hx-target="this" hx-swap="outerHTML">
  <p class="text-sm uppercase tracking-wide text-slate-500">{{ vocab.language }}</p>
  <h1 class="mt-2 text-3xl font-semibold text-slate-900">{{ vocab.token }}</h1>
  <p class="mt-4 text-slate-700">{{ vocab.definition }}</p>
  {% if vocab.example_sentence %}
  <p class="mt-2 italic text-slate-500">{{ vocab.example_sentence }}</p>
  {% endif %}

  <div class="mt-6 grid grid-cols-2 gap-2">
    <button class="rounded-md bg-rose-600 px-3 py-2 text-white"
            hx-post="/review/{{ review.id }}/rate" hx-vals='{"quality": 0}'>Again</button>
    <button class="rounded-md bg-amber-600 px-3 py-2 text-white"
            hx-post="/review/{{ review.id }}/rate" hx-vals='{"quality": 2}'>Hard</button>
    <button class="rounded-md bg-emerald-600 px-3 py-2 text-white"
            hx-post="/review/{{ review.id }}/rate" hx-vals='{"quality": 4}'>Good</button>
    <button class="rounded-md bg-sky-600 px-3 py-2 text-white"
            hx-post="/review/{{ review.id }}/rate" hx-vals='{"quality": 5}'>Easy</button>
  </div>
</div>
```

- [ ] **Step 3**: Commit — `feat: add GET /review/{id}/reveal and rating partial`.

---

## Task 4: `POST /review/{id}/rate` — SM-2 update + next card

- [ ] **Step 1**: Append:

```python
@router.post("/review/{review_id}/rate")
async def review_rate(
    review_id: UUID,
    request: Request,
    quality: int = Form(...),
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
) -> Response:
    try:
        quality_enum = ReviewQuality(quality)
    except ValueError:
        raise HTTPException(status_code=422, detail="invalid quality")

    review = (
        await session.execute(
            select(Review).where(Review.id == review_id, Review.user_id == user.id)
        )
    ).scalar_one_or_none()
    if review is None:
        raise HTTPException(status_code=404)

    state = ReviewState(
        ease_factor=review.ease_factor,
        interval_days=review.interval_days,
        repetitions=review.repetitions,
    )
    update = compute_next_review(state, quality_enum)
    now = datetime.now(timezone.utc)
    review.ease_factor = update.ease_factor
    review.interval_days = update.interval_days
    review.repetitions = update.repetitions
    review.last_reviewed_at = now
    review.due_at = now + timedelta(days=update.interval_days)
    await session.commit()

    next_review = await _next_due_review(session, user.id, now)
    if next_review is None:
        return templates.TemplateResponse(request, "partials/done.html")
    return templates.TemplateResponse(
        request,
        "partials/card.html",
        {"review": next_review, "vocab": next_review.vocab_item},
    )
```

`quality` is read via `Form(...)` because HTMX form submission posts `application/x-www-form-urlencoded` by default (with `hx-vals` it's encoded as form data unless `hx-ext="json-enc"` is used). HTMX 2.x sends `hx-vals` as form fields by default — `Form(...)` is the right read.

- [ ] **Step 2**: Commit — `feat: add POST /review/{id}/rate with SM-2 persistence`.

---

## Task 5: Wire the router

- [ ] **Step 1**: Edit `apps/api/app/api/router.py`:

```python
from fastapi import APIRouter

from app.api.reviews import router as reviews_router

router = APIRouter()
router.include_router(reviews_router)
```

(If A/B/C/D are merging in order A→B→C→D, this is a clean addition. If another slice has already added an include line, append in alphabetical order: dashboard, reviews, vocab.)

- [ ] **Step 2**: Commit — `feat: wire reviews router into app.api.router`.

---

## Task 6: Tests

- [ ] **Step 1**: Create `apps/api/tests/api/test_reviews.py` with these test cases:

```python
def test_get_review_returns_oldest_due_card_for_user(...): ...
def test_get_review_renders_done_when_no_due_reviews(...): ...
def test_get_review_excludes_suspended_reviews(...): ...
def test_get_review_excludes_other_users_reviews(...): ...
def test_get_review_treats_null_due_at_as_due(...): ...
def test_reveal_returns_partial_with_definition(...): ...
def test_reveal_404_when_not_owner(...): ...
def test_rate_updates_review_with_sm2_output(...): ...
    # Insert review with ease_factor=2.5, interval_days=0, repetitions=0; POST quality=4;
    # assert post-state matches compute_next_review's output (don't reimplement SM-2 — call it).
def test_rate_quality_again_resets_repetitions(...): ...
def test_rate_advances_to_next_due_card_in_response(...): ...
def test_rate_returns_done_partial_when_no_more_due(...): ...
def test_rate_rejects_invalid_quality_value(...): ...
    # POST quality=3 → 422.
def test_rate_404_when_not_owner(...): ...
def test_rate_sets_last_reviewed_at_and_due_at(...): ...
    # assert last_reviewed_at within ~1s of now; due_at == last_reviewed_at + interval_days.
```

Use the existing async test session pattern. Override the `get_current_user` FastAPI dep to return a fixed user fixture per test (this is the cleanest way to test multi-user isolation):

```python
from app.api.deps import get_current_user
app.dependency_overrides[get_current_user] = lambda: test_user
```

- [ ] **Step 2**: Commit — `test: cover review session GET, reveal, and rate flows`.

---

## Task 7: Verification + PR

- [ ] **Step 1**: Tests:
```
uv run pytest apps/api/tests/api/test_reviews.py -v
```

- [ ] **Step 2**: Lint:
```
pnpm lint
```

- [ ] **Step 3**: Browser smoke (requires Postgres up + at least one VocabItem with a Review row for `dev@local`):
```
pnpm dev
open http://localhost:8000/review
```
Click "Reveal definition" → 4 rating buttons appear. Click any rating → card swaps to the next due (or to the "All caught up" state). Refresh `/review` and confirm the rated card's `due_at` was pushed forward (should not appear immediately unless quality=0).

- [ ] **Step 4**: Open PR titled `feat: review session UI (Slice B)`. Squash-merge after review.

---

## Acceptance criteria

- `GET /review` renders a card for the oldest due review owned by `current_user`, or the done state if none.
- `GET /review/{id}/reveal` returns the rating partial when the review belongs to the user; 404 otherwise.
- `POST /review/{id}/rate` accepts quality ∈ {0, 2, 4, 5}, updates the row via `compute_next_review`, sets `last_reviewed_at` and `due_at`, and returns either the next card partial or the done partial. Invalid quality → 422.
- HTMX swaps `#review-card` in place — no full page reload between cards.
- Suspended reviews are never returned. Reviews owned by other users are never returned.
- All tests in `apps/api/tests/api/test_reviews.py` pass; ruff + mypy clean.

## Notes / gotchas

- **Dependency override seam.** Tests should override `get_current_user`, not patch DB queries. When real auth lands, the same override pattern still works.
- **`due_at` semantics.** `null` means "never reviewed → immediately due". After the first rating, `due_at` is always set. The `_next_due_review` query treats both as due.
- **`hx-vals` form encoding.** HTMX 2.x sends `hx-vals` as form fields with the default content-type. `quality` is read with `Form(...)`. If you switch to JSON encoding, change to `quality: int = Body(..., embed=True)` and add `hx-ext="json-enc"`.
- **`joinedload` on the relationship.** Without the eager load, `review.vocab_item.token` triggers a lazy load — and `lazy="raise"` will throw inside the template. Keep `joinedload(Review.vocab_item)` on every read path.
- **Timezone.** All `datetime.now()` calls use `timezone.utc`. The `due_at` column is `DateTime(timezone=True)` (see `apps/api/app/models/review.py:37`).
- **No new schemas.** This slice does not add or modify pydantic schemas — `ReviewState`, `ReviewQuality`, and `compute_next_review` are reused as-is.
