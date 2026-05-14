# Slice C — Dashboard + stats page

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Server-rendered dashboard at `GET /dashboard` showing four numbers — due-today count, total reviews completed, current streak (consecutive UTC days with at least one review), and the last 5 ratings — for the current user. `GET /` redirects to `/dashboard` so the index has a meaningful destination after Slice 0 removed the placeholder.

**Architecture:** Pydantic schemas under `app/schemas/stats.py` describe the read shape. A pure-ish service `compute_user_stats` in `app/services/stats.py` runs the four queries and returns a `UserStats`. The `app/api/dashboard.py` sub-router renders `pages/dashboard.html` with that struct. No HTMX — initial page load only; refresh on navigation.

**Prerequisite:** Slice 0 merged (provides `get_current_user`, `templates`, `app.api.router`).

**Tech stack:** FastAPI async, SQLAlchemy 2.0 async, Jinja2, Tailwind compiled output. Reads `Review.user_id`, `Review.last_reviewed_at`, `Review.due_at`, `Review.suspended`, `Review.interval_days`, `VocabItem.token`.

---

## File Structure

**Create:**
- `apps/api/app/schemas/stats.py` — `RecentRating`, `UserStats`
- `apps/api/app/services/stats.py` — `compute_user_stats(session, user, *, today=None) -> UserStats`
- `apps/api/app/api/dashboard.py` — sub-router with `GET /dashboard` and `GET /` redirect
- `apps/api/templates/pages/dashboard.html` — Tailwind-styled stats page
- `apps/api/alembic/versions/0003_add_user_timezone.py` — new migration (depends on `0002_add_enrichment_tracking` from Slice A)
- `apps/api/tests/services/test_stats.py`
- `apps/api/tests/api/test_dashboard.py`

**Modify:**
- `apps/api/app/models/user.py` — add `timezone: Mapped[str]` column (default `"UTC"`)
- `apps/api/app/api/router.py` — add `router.include_router(dashboard_router)`

**No edits to:** any other model, existing service, `main.py`, `base.html`.

---

## Task 0: User.timezone column + migration

- [ ] **Step 1**: Edit `apps/api/app/models/user.py` to add the column:

```python
timezone: Mapped[str] = mapped_column(String(64), nullable=False, server_default="UTC")
```

The `server_default="UTC"` lets the migration backfill existing rows without a separate UPDATE.

- [ ] **Step 2**: Create `apps/api/alembic/versions/0003_add_user_timezone.py`:

```python
"""add user.timezone

Revision ID: 0003
Revises: 0002
"""
from alembic import op
import sqlalchemy as sa

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("timezone", sa.String(length=64), nullable=False, server_default="UTC"),
    )


def downgrade() -> None:
    op.drop_column("users", "timezone")
```

- [ ] **Step 3**: After the migration is applied locally, manually set your dev user's timezone:

```sql
UPDATE users SET timezone='Asia/Jakarta' WHERE email='dev@local';
```

(Keeping env-specific data out of migrations — the migration only sets the default.)

- [ ] **Step 4**: Commit — `feat: add User.timezone column (default UTC)`. See [ADR-0004](../../../docs/adr/0004-per-user-timezone-on-user-model.md).

---

## Task 1: Schemas

- [ ] **Step 1**: Create `apps/api/app/schemas/stats.py`:

```python
from datetime import datetime
from pydantic import BaseModel, Field


class RecentRating(BaseModel):
    token: str
    interval_days: int
    reviewed_at: datetime


class UserStats(BaseModel):
    due_today: int = Field(ge=0)
    total_reviews: int = Field(ge=0)
    current_streak: int = Field(ge=0)
    recent: list[RecentRating] = Field(max_length=5)
```

- [ ] **Step 2**: Commit — `feat: add UserStats and RecentRating schemas`.

---

## Task 2: Stats service

- [ ] **Step 1**: Create `apps/api/app/services/stats.py`:

```python
from __future__ import annotations

from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.review import Review
from app.models.user import User
from app.models.vocab_item import VocabItem
from app.schemas.stats import RecentRating, UserStats


async def compute_user_stats(
    session: AsyncSession,
    user: User,
    *,
    today: date | None = None,
) -> UserStats:
    user_tz = ZoneInfo(user.timezone)
    today = today or datetime.now(user_tz).date()
    start_of_today_local = datetime.combine(today, datetime.min.time(), tzinfo=user_tz)
    end_of_today_local = start_of_today_local + timedelta(days=1)

    due_today = (await session.execute(
        select(func.count(Review.id))
        .join(VocabItem, Review.vocab_item_id == VocabItem.id)
        .where(
            Review.user_id == user.id,
            Review.suspended.is_(False),
            Review.due_at < end_of_today_local,   # tz-aware comparison; Postgres normalizes to UTC
            VocabItem.definition != "",            # hide pending enrichment — see ADR-0001
        )
    )).scalar_one()

    total_reviews = (await session.execute(
        select(func.count(Review.id))
        .where(Review.user_id == user.id, Review.last_reviewed_at.is_not(None))
    )).scalar_one()

    # Convert UTC timestamps to the user's tz before truncating to a date.
    # Postgres: timezone(tz_name, timestamptz) → timestamp in that tz.
    local_review_date = func.date(func.timezone(user.timezone, Review.last_reviewed_at))
    review_dates = (await session.execute(
        select(local_review_date)
        .where(Review.user_id == user.id, Review.last_reviewed_at.is_not(None))
        .group_by(local_review_date)
        .order_by(local_review_date.desc())
    )).scalars().all()

    streak = _compute_streak(set(review_dates), today)

    recent_rows = (await session.execute(
        select(VocabItem.token, Review.interval_days, Review.last_reviewed_at)
        .join(VocabItem, Review.vocab_item_id == VocabItem.id)
        .where(Review.user_id == user.id, Review.last_reviewed_at.is_not(None))
        .order_by(Review.last_reviewed_at.desc())
        .limit(5)
    )).all()
    recent = [
        RecentRating(token=t, interval_days=i, reviewed_at=r) for (t, i, r) in recent_rows
    ]

    return UserStats(
        due_today=int(due_today),
        total_reviews=int(total_reviews),
        current_streak=streak,
        recent=recent,
    )


def _compute_streak(dates_with_reviews: set[date], today: date) -> int:
    """Walk back from `today` (with a 1-day grace if today is empty)
    counting consecutive days that have at least one review."""
    if not dates_with_reviews:
        return 0
    cursor = today if today in dates_with_reviews else today - timedelta(days=1)
    if cursor not in dates_with_reviews:
        return 0
    streak = 0
    while cursor in dates_with_reviews:
        streak += 1
        cursor = cursor - timedelta(days=1)
    return streak
```

- [ ] **Step 2**: Create `apps/api/tests/services/test_stats.py`:

```python
def test_due_today_counts_only_due_and_unsuspended(...):
    # Mix of: due in past, due in future, suspended-due-in-past. Only the first counts.

def test_due_today_excludes_unenriched_vocab(...):
    # Two due reviews for the user, but one's VocabItem has definition == "". Count = 1.

def test_total_reviews_counts_only_reviewed(...):
    # Reviews with last_reviewed_at IS NOT NULL count; others don't.

def test_streak_zero_when_no_reviews(...): ...
def test_streak_one_when_only_today_reviewed(...): ...
def test_streak_continues_through_yesterday_when_today_empty(...):
    # last_reviewed_at on yesterday + day-before; today empty → streak=2.
def test_streak_breaks_on_two_day_gap(...):
    # last_reviewed_at on today + 3-days-ago → streak=1.
def test_streak_uses_user_timezone_not_utc(...):
    # User.timezone = "Asia/Jakarta" (UTC+7). Insert two reviews at the same UTC instant
    # that straddle UTC midnight but land on the same Jakarta-local day. Assert streak=1,
    # not 2 (UTC counting would say 2).
def test_streak_uses_user_timezone_for_today_grace(...):
    # User.timezone = "America/New_York" (UTC-5). At a moment when local-today has no
    # reviews but UTC-today does, assert the streak still counts back from local-today.
def test_recent_returns_last_five_ordered_desc(...):
    # Insert 7 reviews across different times; assert returned 5 are the newest.
def test_compute_user_stats_isolated_per_user(...):
    # Two users; each only sees their own counts.
def test_compute_user_stats_handles_user_with_no_reviews(...):
    # All zeros, empty recent.
```

- [ ] **Step 3**: Commit — `feat: add compute_user_stats service`.

---

## Task 3: Dashboard router

- [ ] **Step 1**: Create `apps/api/app/api/dashboard.py`:

```python
from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, templates
from app.core.db import get_session
from app.models.user import User
from app.services.stats import compute_user_stats

router = APIRouter()


@router.get("/")
async def index() -> RedirectResponse:
    return RedirectResponse(url="/dashboard", status_code=307)


@router.get("/dashboard")
async def dashboard(
    request: Request,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
) -> Response:
    stats = await compute_user_stats(session, user)
    return templates.TemplateResponse(
        request,
        "pages/dashboard.html",
        {"stats": stats, "user": user},
    )
```

`status_code=307` preserves method on redirect (matches HTTP semantics for index pages).

- [ ] **Step 2**: Commit — `feat: add dashboard router with GET / redirect and GET /dashboard`.

---

## Task 4: Dashboard template

- [ ] **Step 1**: Create `apps/api/templates/pages/dashboard.html`:

```html
{% extends "base.html" %}
{% block title %}Dashboard — RecallAI{% endblock %}
{% block content %}
<main class="max-w-3xl mx-auto px-4 py-12">
  <header class="flex items-center justify-between">
    <h1 class="text-2xl font-semibold text-slate-900">Dashboard</h1>
    <a href="/review" class="rounded-md bg-slate-900 px-4 py-2 text-white hover:bg-slate-700">
      Start review
    </a>
  </header>

  <section class="mt-8 grid grid-cols-3 gap-4">
    <div class="rounded-lg border border-slate-200 bg-white p-6">
      <p class="text-sm uppercase tracking-wide text-slate-500">Due today</p>
      <p class="mt-2 text-3xl font-semibold text-slate-900">{{ stats.due_today }}</p>
    </div>
    <div class="rounded-lg border border-slate-200 bg-white p-6">
      <p class="text-sm uppercase tracking-wide text-slate-500">Total reviews</p>
      <p class="mt-2 text-3xl font-semibold text-slate-900">{{ stats.total_reviews }}</p>
    </div>
    <div class="rounded-lg border border-slate-200 bg-white p-6">
      <p class="text-sm uppercase tracking-wide text-slate-500">Streak</p>
      <p class="mt-2 text-3xl font-semibold text-slate-900">{{ stats.current_streak }}</p>
    </div>
  </section>

  <section class="mt-8">
    <h2 class="text-lg font-semibold text-slate-900">Recent</h2>
    {% if stats.recent %}
    <ul class="mt-3 divide-y divide-slate-200 rounded-lg border border-slate-200 bg-white">
      {% for r in stats.recent %}
      <li class="flex items-center justify-between px-4 py-3">
        <span class="font-medium text-slate-900">{{ r.token }}</span>
        <span class="text-sm text-slate-500">
          interval {{ r.interval_days }}d · {{ r.reviewed_at.strftime("%Y-%m-%d %H:%M") }} UTC
        </span>
      </li>
      {% endfor %}
    </ul>
    {% else %}
    <p class="mt-3 text-slate-500">No reviews yet — head over to <a class="underline" href="/review">review</a>.</p>
    {% endif %}
  </section>
</main>
{% endblock %}
```

- [ ] **Step 2**: Commit — `feat: add dashboard page template`.

---

## Task 5: Wire the router

- [ ] **Step 1**: Edit `apps/api/app/api/router.py` — add an import + include for the dashboard router:

```python
from fastapi import APIRouter

from app.api.dashboard import router as dashboard_router
# from app.api.reviews import router as reviews_router    # if Slice B already merged
# from app.api.vocab import router as vocab_router        # if Slice D already merged

router = APIRouter()
router.include_router(dashboard_router)
# router.include_router(reviews_router)
# router.include_router(vocab_router)
```

Order of includes is alphabetical by file (dashboard, reviews, vocab) — that's the convention this batch follows so the squash-merge order A→B→C→D produces a clean `router.py`.

- [ ] **Step 2**: Commit — `feat: wire dashboard router into app.api.router`.

---

## Task 6: API tests

- [ ] **Step 1**: Create `apps/api/tests/api/test_dashboard.py`:

```python
def test_dashboard_renders_due_today_count(...):
    # Seed 2 due reviews + 1 not-yet-due. Assert the rendered HTML contains "Due today" and "2".

def test_dashboard_isolated_per_user(...):
    # User A has 5 due, User B has 1 due. Override get_current_user → B. HTML contains "1".

def test_dashboard_renders_recent_tokens_in_descending_order(...):
    # Seed 3 reviews on different timestamps. Assert tokens appear in newest-first order in the HTML.

def test_index_redirects_to_dashboard(...):
    # GET / → 307 with Location header /dashboard.

def test_dashboard_handles_user_with_no_reviews(...):
    # All zeros render; "No reviews yet" text appears.
```

Use `client.get("/", follow_redirects=False)` for the redirect test. For HTML body assertions, parse with `from bs4 import BeautifulSoup` (already a transitive dep, or add `beautifulsoup4` to dev deps if not — check with `uv pip list` first; if absent, fall back to `assert "Due today" in response.text and ">2<" in response.text`).

- [ ] **Step 2**: Commit — `test: cover dashboard rendering and isolation`.

---

## Task 7: Verification + PR

- [ ] **Step 1**: Tests:
```
uv run pytest apps/api/tests/services/test_stats.py apps/api/tests/api/test_dashboard.py -v
```

- [ ] **Step 2**: Lint:
```
pnpm lint
```

- [ ] **Step 3**: Browser smoke (Postgres up, dev user has at least one Review row):
```
pnpm dev
open http://localhost:8000/             # → 307 redirect → /dashboard
open http://localhost:8000/dashboard
```
Confirm the four cards render and "Recent" shows your most recent ratings.

- [ ] **Step 4**: Open PR titled `feat: dashboard + stats (Slice C)`. Squash-merge after review.

---

## Acceptance criteria

- `GET /` redirects to `/dashboard` with 307.
- `GET /dashboard` returns 200 with the four stat cards and a "Recent" list (max 5 items, newest first).
- `due_today` counts only reviews with `due_at < end_of_today_utc`, `suspended is False`, and `vocab_item.definition != ""` (pending-enrichment cards are excluded — see ADR-0001), owned by `current_user`.
- `total_reviews` counts only `Review` rows with `last_reviewed_at IS NOT NULL` for `current_user`.
- `current_streak` matches `_compute_streak` semantics: 0 if no reviews, allows a 1-day grace when today has no review yet, breaks on any gap. "Today" and review-date bucketing are evaluated in `User.timezone` (default `UTC`) — see [ADR-0004](../../../docs/adr/0004-per-user-timezone-on-user-model.md).
- All tests in `tests/services/test_stats.py` and `tests/api/test_dashboard.py` pass; ruff + mypy clean.
- `pnpm test` (full suite) is green.

## Notes / gotchas

- **`func.date(func.timezone(user.timezone, Review.last_reviewed_at))`** in postgres returns a `date` value bucketed in the user's local timezone. The set comparison in `_compute_streak` relies on this being a `date`, not a `datetime`. If the test database is sqlite (check `tests/conftest.py`), `func.timezone` is unsupported — switch the test DB to Postgres (testcontainers) or stub the streak test by injecting `today` plus a precomputed `set[date]` directly into `_compute_streak`.
- **Timezone.** Streak and `due_today` are computed in `User.timezone`. Default is `"UTC"`; the dev user is manually set to `"Asia/Jakarta"` post-migration (see Task 0 step 3). When real auth lands, the OAuth flow should populate `timezone` from the browser (`Intl.DateTimeFormat().resolvedOptions().timeZone`).
- **`recent` cap.** `Field(max_length=5)` enforces ≤5; the query uses `.limit(5)`. Both must agree.
- **Grace day in streak.** If `today` has no review yet, the streak still counts back from `today - 1`. This avoids a streak "breaking" mid-day before the user reviews. Tested explicitly.
- **`/` route** is registered here. Do **not** also register it elsewhere — Slice 0 removed the inline `/` from `main.py` precisely so this slice can own it.
- **No HTMX on this page.** Dashboard is a static read; future "live update" is a follow-up.
