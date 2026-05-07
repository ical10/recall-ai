# Slice A — Daily content generation pipeline

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Wire a Celery-beat nightly task that selects unenriched VocabItems, calls the existing `LLMClient` with `SimpleVocabExample`, and persists the validated `definition` and `example_sentence` back to the row. This is the first end-to-end use of the LLM harness against real data.

**Architecture:** Celery 5 tasks are sync (per CLAUDE.md line 60), so the worker uses a sync SQLAlchemy engine on the `psycopg` driver — there's no benefit to running async inside a worker that processes a small batch sequentially. Selection logic, enrichment logic, and the worker entrypoint are split into three files so each is independently unit-testable. The beat schedule fires the task daily at 03:00 UTC; the same task can be invoked on demand via `celery call`.

**Prerequisite:** Slice 0 (current-user dep + router scaffold) merged to `main`. Slice A does **not** touch `app/api/router.py` or any sub-router — it adds a worker, services, a sync DB module, and a beat-schedule entry on `core/celery_app.py`.

**Tech stack:** Celery 5 (already wired), SQLAlchemy 2.0 sync (`psycopg[binary]>=3.2`), existing `LLMClient` (`app/services/llm.py:39`), `SimpleVocabExample` schema (`app/schemas/llm.py:10`).

---

## File Structure

**Create:**
- `apps/api/app/core/db_sync.py` — sync engine + `SyncSessionLocal` derived from `Settings.database_url`
- `apps/api/app/services/selection.py` — `select_unenriched(session, limit) -> list[VocabItem]`
- `apps/api/app/services/enrichment.py` — `enrich_vocab_item(item, llm) -> SimpleVocabExample`
- `apps/api/app/workers/content_gen.py` — `@celery_app.task` entrypoint
- `apps/api/tests/services/test_selection.py`
- `apps/api/tests/services/test_enrichment.py`
- `apps/api/tests/workers/__init__.py`
- `apps/api/tests/workers/test_content_gen.py`

**Modify:**
- `apps/api/app/core/celery_app.py` — add `beat_schedule` + `imports`
- `apps/api/tests/core/test_celery_app.py` — assert beat schedule registers
- `pyproject.toml` — add `psycopg[binary]>=3.2`
- `uv.lock` — re-resolved automatically

**No edits to:** `app/api/router.py`, models, existing schemas, templates, migrations.

---

## Task 1: Add `psycopg[binary]` and sync DB module

- [ ] **Step 1**: Add `psycopg[binary]>=3.2` to `pyproject.toml` under `[project] dependencies`. Run `uv lock` from the repo root to refresh `uv.lock`.

- [ ] **Step 2**: Create `apps/api/app/core/db_sync.py`:

```python
from sqlalchemy import create_engine
from sqlalchemy.engine.url import make_url
from sqlalchemy.orm import sessionmaker, Session

from app.core.config import get_settings


def to_sync_url(url: str) -> str:
    parsed = make_url(url)
    if parsed.drivername in {"postgresql+asyncpg", "postgresql"}:
        parsed = parsed.set(drivername="postgresql+psycopg")
    return parsed.render_as_string(hide_password=False)


sync_engine = create_engine(
    to_sync_url(get_settings().database_url),
    echo=False,
    future=True,
)

SyncSessionLocal: sessionmaker[Session] = sessionmaker(
    sync_engine, expire_on_commit=False
)
```

`to_sync_url` is the inverse of `app.core.db.to_async_url` (see `apps/api/app/core/db.py:14`) — both accept the same source URL formats.

- [ ] **Step 3**: Commit — `chore: add psycopg dep and sync engine for celery workers`.

---

## Task 2: Selection service

- [ ] **Step 1**: Create `apps/api/app/services/selection.py`:

```python
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.models.vocab_item import VocabItem


def select_unenriched(session: Session, limit: int) -> list[VocabItem]:
    """Return up to `limit` VocabItems missing definition or example_sentence,
    ordered by created_at ASC (oldest first)."""
    if limit <= 0:
        return []
    stmt = (
        select(VocabItem)
        .where(or_(VocabItem.definition == "", VocabItem.example_sentence.is_(None)))
        .order_by(VocabItem.created_at.asc())
        .limit(limit)
    )
    return list(session.execute(stmt).scalars().all())
```

`VocabItem.definition` is `nullable=False` (see `apps/api/app/models/vocab_item.py:17`), so "missing definition" is encoded as empty string. The seed script (Slice D) inserts placeholder rows with `definition=""` to mark them as needing enrichment.

- [ ] **Step 2**: Create `apps/api/tests/services/test_selection.py`:

```python
def test_select_unenriched_returns_only_items_missing_definition_or_example(...): ...
def test_select_unenriched_respects_limit_and_orders_by_created_at(...): ...
def test_select_unenriched_returns_empty_list_when_limit_zero(...): ...
def test_select_unenriched_returns_empty_list_when_all_enriched(...): ...
```

Tests use the existing async test session pattern (`tests/conftest.py` provides one). For sync access in this test file, use a sync session bound to the same test database — read `tests/conftest.py` to see how previous slices handled this. If only async is provided, wrap calls in `asyncio.get_event_loop().run_in_executor` or add a small sync fixture.

- [ ] **Step 3**: Commit — `feat: add select_unenriched service`.

---

## Task 3: Enrichment service

- [ ] **Step 1**: Create `apps/api/app/services/enrichment.py`:

```python
from app.models.vocab_item import VocabItem
from app.schemas.llm import SimpleVocabExample
from app.services.llm import LLMClient

PROMPT_TEMPLATE = (
    "Define the {language} word '{token}' for an English-speaking ESL learner. "
    "Return JSON with these fields:\n"
    '  - "token": the word itself, exactly as given\n'
    '  - "definition": 1-2 sentence definition (20-500 chars)\n'
    '  - "example": one example sentence containing the word (10-500 chars)\n'
    "Return only the JSON object, no commentary."
)


def enrich_vocab_item(item: VocabItem, llm: LLMClient) -> SimpleVocabExample:
    prompt = PROMPT_TEMPLATE.format(language=item.language, token=item.token)
    return llm.complete(prompt, SimpleVocabExample)
```

This service is pure — no DB writes. The worker layer is responsible for persisting the result. `LLMValidationFailure` propagates and is caught at the worker boundary.

- [ ] **Step 2**: Create `apps/api/tests/services/test_enrichment.py`:

```python
def test_enrich_vocab_item_calls_llm_with_token_and_language(...):
    # MagicMock LLMClient; assert prompt contains item.token and item.language.

def test_enrich_vocab_item_returns_validated_simple_vocab_example(...):
    # Stub LLMClient.complete to return SimpleVocabExample(...); assert returned object.

def test_enrich_vocab_item_propagates_llm_validation_failure(...):
    # Stub LLMClient.complete to raise LLMValidationFailure; assert it bubbles.
```

- [ ] **Step 3**: Commit — `feat: add enrich_vocab_item service`.

---

## Task 4: Worker task

- [ ] **Step 1**: Create `apps/api/app/workers/content_gen.py`:

```python
from __future__ import annotations

import logging

from celery import Task

from app.core.celery_app import celery_app
from app.core.db_sync import SyncSessionLocal
from app.services.enrichment import enrich_vocab_item
from app.services.llm import LLMClient, LLMValidationFailure
from app.services.selection import select_unenriched

logger = logging.getLogger(__name__)


@celery_app.task(name="content_gen.run_daily", bind=True, max_retries=3)
def run_daily(self: Task, batch_size: int = 25) -> dict[str, int]:
    succeeded = 0
    failed = 0
    with SyncSessionLocal() as session:
        items = select_unenriched(session, batch_size)
        if not items:
            return {"succeeded": 0, "failed": 0}
        llm = LLMClient()
        for item in items:
            try:
                result = enrich_vocab_item(item, llm)
                item.definition = result.definition
                item.example_sentence = result.example
                succeeded += 1
            except LLMValidationFailure as e:
                logger.warning(
                    "content_gen_item_failed",
                    extra={"vocab_item_id": str(item.id), "attempts": e.attempts},
                )
                failed += 1
        session.commit()
    return {"succeeded": succeeded, "failed": failed}
```

**Why `bind=True, max_retries=3`:** the harness in `LLMClient.complete` already retries validation failures up to 3 times per item. The Celery `max_retries` here covers infrastructure errors (network, DB), not LLM validation — those are caught and counted. We do **not** call `self.retry()` automatically; per-item failures are recorded in the return dict for monitoring. If you want the whole task to retry on session.commit() failures, wrap the commit and call `self.retry(exc=exc)` — leave that out unless requested.

- [ ] **Step 2**: Create `apps/api/tests/workers/__init__.py` (empty) and `apps/api/tests/workers/test_content_gen.py`:

```python
def test_run_daily_persists_definition_and_example_to_vocab_item(...):
    # Insert 2 unenriched VocabItems; monkeypatch LLMClient to return canned SimpleVocabExample;
    # call run_daily(batch_size=2); assert items now have non-empty definition/example_sentence.

def test_run_daily_skips_failed_items_and_continues_batch(...):
    # 3 items; LLMClient raises LLMValidationFailure on the 2nd. Assert succeeded=2, failed=1
    # and the 1st and 3rd items got persisted.

def test_run_daily_returns_zero_counts_when_no_unenriched(...):
    # Empty selection; assert {"succeeded":0,"failed":0} and LLMClient is not constructed.

def test_run_daily_respects_batch_size(...):
    # 50 items, batch_size=5; assert exactly 5 LLMClient.complete calls.
```

For the LLMClient monkeypatch, target `app.workers.content_gen.LLMClient` (where it's imported), not the original module. Tests use `SyncSessionLocal` against the test DB — set up via the same fixture as `test_selection`.

- [ ] **Step 3**: Commit — `feat: add content_gen.run_daily celery task`.

---

## Task 5: Beat schedule + autodiscover

- [ ] **Step 1**: Edit `apps/api/app/core/celery_app.py`:

```python
from celery import Celery
from celery.schedules import crontab

from app.core.config import get_settings

_settings = get_settings()

celery_app = Celery(
    "recall_ai",
    broker=_settings.redis_url,
    backend=_settings.redis_url,
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    imports=("app.workers.content_gen",),
    beat_schedule={
        "content-gen-daily": {
            "task": "content_gen.run_daily",
            "schedule": crontab(hour=3, minute=0),
            "kwargs": {"batch_size": 25},
        },
    },
)
```

Use `imports=(...)` (tuple in `conf.update`) rather than `celery_app.autodiscover_tasks(...)` — the workers directory is a regular package, not an installed app, so `imports` is the simplest route.

- [ ] **Step 2**: Extend `apps/api/tests/core/test_celery_app.py` with:

```python
def test_imports_includes_content_gen():
    assert "app.workers.content_gen" in celery_app.conf.imports

def test_beat_schedule_registers_nightly_content_gen():
    schedule = celery_app.conf.beat_schedule
    assert "content-gen-daily" in schedule
    entry = schedule["content-gen-daily"]
    assert entry["task"] == "content_gen.run_daily"
    assert entry["kwargs"] == {"batch_size": 25}
    # crontab(hour=3, minute=0) — assert hour and minute fields:
    sched = entry["schedule"]
    assert 3 in sched.hour and 0 in sched.minute
```

- [ ] **Step 3**: Commit — `feat: schedule content_gen.run_daily nightly via celery beat`.

---

## Task 6: Verification + PR

- [ ] **Step 1**: Run targeted tests:
```
uv run pytest apps/api/tests/services/test_selection.py apps/api/tests/services/test_enrichment.py apps/api/tests/workers/test_content_gen.py apps/api/tests/core/test_celery_app.py -v
```

- [ ] **Step 2**: Lint:
```
pnpm lint
```

- [ ] **Step 3**: Local end-to-end smoke (requires Postgres + Redis running, `LLM_*` env vars set):
```
# Terminal 1: web (just to keep DB engine warm — optional)
pnpm dev

# Terminal 2: worker
pnpm worker

# Terminal 3: trigger immediately
uv run --project . celery -A app.core.celery_app:celery_app --workdir apps/api call content_gen.run_daily --kwargs '{"batch_size":2}'
```
Insert two `VocabItem` rows with empty `definition` first (psql or seed script from Slice D once it lands; for now a one-liner via `uv run python -c "..."`). After the task runs, those rows should have populated `definition` and `example_sentence`.

- [ ] **Step 4**: Open PR titled `feat: daily content generation pipeline (Slice A)`. Squash-merge after review.

---

## Acceptance criteria

- `pnpm test` (full suite) is green.
- `pnpm lint` is clean.
- `pnpm beat` logs `Scheduler: Sending due task content-gen-daily (content_gen.run_daily)` at the configured time.
- `celery call content_gen.run_daily --kwargs '{"batch_size":2}'` returns `{"succeeded": 2, "failed": 0}` against two seeded unenriched items, and the rows now hold the LLM-generated definition + example.
- The task is idempotent: running it again with no unenriched rows returns `{"succeeded": 0, "failed": 0}` without invoking the LLM.

## Notes / gotchas

- **Sync vs async DB.** Celery 5 tasks are sync. Don't `asyncio.run` inside the task — use `SyncSessionLocal`. `to_sync_url` strips the `+asyncpg` driver suffix and swaps in `+psycopg`.
- **`psycopg[binary]` install.** The `[binary]` extra ships precompiled wheels. If the production environment can build from source, `psycopg>=3.2` is enough. Keep `[binary]` until you have a reason to drop it.
- **`LLMClient.complete` is sync** — the existing client is OpenAI's sync `OpenAI` client (see `apps/api/app/services/llm.py:32`), which fits naturally inside a Celery task.
- **Idempotent enrichment.** `select_unenriched` keys off `definition == ""` OR `example_sentence IS NULL`. Once a row is enriched it disappears from the selection; rerunning the task is safe.
- **Logging.** `LLMClient` already logs `llm_call` and `llm_validation_failed` (`apps/api/app/services/llm.py:51,67`). The worker logs only `content_gen_item_failed` so the per-item attempt count is preserved.
- **No model schema change.** This slice does not touch the database schema. If you later want to track an `enrichment_attempted_at` column, write a new migration in a follow-up slice — never edit `0001_initial`.
