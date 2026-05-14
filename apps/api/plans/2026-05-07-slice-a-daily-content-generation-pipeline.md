# Slice A — Daily content generation pipeline

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Wire a Celery-beat nightly task that selects unenriched VocabItems, calls the existing `LLMClient` with `SimpleVocabExample`, and persists the validated `definition` and `example_sentence` back to the row. This is the first end-to-end use of the LLM harness against real data.

**Architecture:** Celery 5 tasks are sync at the entrypoint, but we reuse the existing async DB stack rather than introducing a parallel sync engine + driver. The worker's task body is a coroutine wrapped in `asyncio.run(...)`, so `select_unenriched` and any future DB-touching service can be shared across web routes and worker tasks without duplication. `LLMClient.complete` stays sync (it wraps the sync `openai.OpenAI` client) and is called directly from inside the async coroutine — sync calls inside async coroutines are legal and fine. The beat schedule fires the task daily; the same task can be invoked on demand via `celery call`. See [ADR-0003](../../../docs/adr/0003-celery-tasks-use-asyncio-run-not-sync-engine.md).

**Prerequisite:** Slice 0 (current-user dep + router scaffold) merged to `main`. Slice A does **not** touch `app/api/router.py` or any sub-router — it adds a worker, two services, and a beat-schedule entry on `core/celery_app.py`. No new dependencies.

**Tech stack:** Celery 5 (already wired), SQLAlchemy 2.0 **async** reused from `app/core/db.py:SessionLocal`, existing `LLMClient` (`app/services/llm.py:39`), `SimpleVocabExample` schema (`app/schemas/llm.py:10`).

---

## File Structure

**Create:**
- `apps/api/app/services/selection.py` — `async def select_unenriched(session, limit) -> list[VocabItem]`
- `apps/api/app/services/enrichment.py` — `def enrich_vocab_item(item, llm) -> SimpleVocabExample` (sync — no DB)
- `apps/api/app/services/content_safety.py` — denylist + `contains_disallowed_term(text) -> bool`
- `apps/api/app/workers/content_gen.py` — sync `@celery_app.task` entrypoint that wraps an async coroutine in `asyncio.run`
- `apps/api/alembic/versions/0002_add_enrichment_tracking.py` — new migration
- `apps/api/tests/services/test_selection.py`
- `apps/api/tests/services/test_enrichment.py`
- `apps/api/tests/services/test_content_safety.py`
- `apps/api/tests/schemas/test_llm.py` — content-safety validator cases
- `apps/api/tests/workers/__init__.py`
- `apps/api/tests/workers/test_content_gen.py`

**Modify:**
- `apps/api/app/models/vocab_item.py` — add `enrichment_attempts: int` and `last_enrichment_attempted_at: datetime | None`
- `apps/api/app/schemas/llm.py` — add a `_no_disallowed_terms` `model_validator` on `SimpleVocabExample`
- `apps/api/app/core/celery_app.py` — add `beat_schedule` + `imports`
- `apps/api/tests/core/test_celery_app.py` — assert beat schedule registers

**No edits to:** `app/api/router.py`, other models, existing schemas, templates, `pyproject.toml`. No new runtime dependencies.

---

## Task 0: Enrichment tracking columns + migration

- [ ] **Step 1**: Edit `apps/api/app/models/vocab_item.py` — add two columns:

```python
from datetime import datetime
from sqlalchemy import DateTime, Integer

# inside class VocabItem:
enrichment_attempts: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
last_enrichment_attempted_at: Mapped[datetime | None] = mapped_column(
    DateTime(timezone=True), nullable=True
)
```

- [ ] **Step 2**: Create `apps/api/alembic/versions/0002_add_enrichment_tracking.py`:

```python
"""add enrichment tracking columns to vocab_items

Revision ID: 0002
Revises: 0001
"""
from alembic import op
import sqlalchemy as sa

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "vocab_items",
        sa.Column("enrichment_attempts", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "vocab_items",
        sa.Column("last_enrichment_attempted_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("vocab_items", "last_enrichment_attempted_at")
    op.drop_column("vocab_items", "enrichment_attempts")
```

- [ ] **Step 3**: Commit — `feat: track enrichment attempts on vocab_items`. See [ADR-0005](../../../docs/adr/0005-enrichment-attempt-tracking.md).

---

## Task 1: Selection service (async)

- [ ] **Step 1**: Create `apps/api/app/services/selection.py`:

```python
from datetime import datetime, timedelta, timezone

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.vocab_item import VocabItem

MAX_ATTEMPTS_BEFORE_COOLDOWN = 3
COOLDOWN_DAYS = 7


async def select_unenriched(session: AsyncSession, limit: int) -> list[VocabItem]:
    """Return up to `limit` VocabItems missing definition or example_sentence and
    not in cooldown, ordered by created_at ASC (oldest first). An item enters
    cooldown after MAX_ATTEMPTS_BEFORE_COOLDOWN consecutive failures; it becomes
    eligible again COOLDOWN_DAYS after its last attempt."""
    if limit <= 0:
        return []
    cooldown_cutoff = datetime.now(timezone.utc) - timedelta(days=COOLDOWN_DAYS)
    stmt = (
        select(VocabItem)
        .where(
            or_(VocabItem.definition == "", VocabItem.example_sentence.is_(None)),
            or_(
                VocabItem.enrichment_attempts < MAX_ATTEMPTS_BEFORE_COOLDOWN,
                VocabItem.last_enrichment_attempted_at.is_(None),
                VocabItem.last_enrichment_attempted_at < cooldown_cutoff,
            ),
        )
        .order_by(VocabItem.created_at.asc())
        .limit(limit)
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())
```

`VocabItem.definition` is `nullable=False` (see `apps/api/app/models/vocab_item.py:17`), so "missing definition" is encoded as the empty string (see [ADR-0001](../../../docs/adr/0001-empty-string-sentinel-for-enrichment-state.md)). The seed script (Slice D) inserts placeholder rows with `definition=""` to mark them as needing enrichment.

- [ ] **Step 2**: Create `apps/api/tests/services/test_selection.py`:

```python
@pytest.mark.asyncio
async def test_select_unenriched_returns_only_items_missing_definition_or_example(...): ...

@pytest.mark.asyncio
async def test_select_unenriched_respects_limit_and_orders_by_created_at(...): ...

@pytest.mark.asyncio
async def test_select_unenriched_returns_empty_list_when_limit_zero(...): ...

@pytest.mark.asyncio
async def test_select_unenriched_returns_empty_list_when_all_enriched(...): ...

@pytest.mark.asyncio
async def test_select_unenriched_skips_items_in_cooldown(...):
    # Item with definition="", enrichment_attempts=3, last_attempted_at=now → not returned.

@pytest.mark.asyncio
async def test_select_unenriched_returns_item_after_cooldown_expires(...):
    # Same as above but last_attempted_at = now - 8 days → returned.

@pytest.mark.asyncio
async def test_select_unenriched_returns_never_attempted_item_regardless_of_attempts_field(...):
    # last_attempted_at IS NULL, enrichment_attempts=0 → returned (the seed-script case).
```

Tests use the existing async test session pattern (`tests/conftest.py` provides one). No sync session needed.

- [ ] **Step 3**: Commit — `feat: add select_unenriched service`.

---

## Task 1.5: Content-safety validator on `SimpleVocabExample`

- [ ] **Step 1**: Create `apps/api/app/services/content_safety.py`:

```python
import re

# Minimal denylist for v1 — slurs and explicit terms that should never appear
# in ESL learning material. Word-boundary regex match (case-insensitive).
# Refine over time as failures surface; this is intentionally short, not exhaustive.
_DISALLOWED_TERMS: tuple[str, ...] = (
    # Add concrete terms here. Kept empty in the repo to avoid checking
    # slurs into version control; populate locally and gitignore, or
    # source from an env var / external file before shipping.
)


def _compile_pattern(terms: tuple[str, ...]) -> re.Pattern[str] | None:
    if not terms:
        return None
    escaped = (re.escape(t) for t in terms)
    return re.compile(rf"\b(?:{'|'.join(escaped)})\b", flags=re.IGNORECASE)


_PATTERN = _compile_pattern(_DISALLOWED_TERMS)


def contains_disallowed_term(text: str) -> bool:
    if _PATTERN is None:
        return False
    return _PATTERN.search(text) is not None
```

The actual denylist is intentionally **not** checked into git — it's the kind of file that benefits from staying out of public diff history. Source it from an external file or env var in production. For v1, leave `_DISALLOWED_TERMS` empty in the repo and populate it locally via a gitignored override file or environment-driven loader before going live. See [ADR-0007](../../../docs/adr/0007-denylist-content-safety-on-llm-output.md).

- [ ] **Step 2**: Edit `apps/api/app/schemas/llm.py` — add a model validator to `SimpleVocabExample`:

```python
from app.services.content_safety import contains_disallowed_term

class SimpleVocabExample(LLMOutput):
    # ... existing fields ...

    @model_validator(mode="after")
    def _no_disallowed_terms(self) -> "SimpleVocabExample":
        for field_name, value in (("definition", self.definition), ("example", self.example)):
            if contains_disallowed_term(value):
                raise ValueError(f"{field_name} contains a disallowed term")
        return self
```

The existing `_example_must_contain_token` validator stays. Both run on `mode="after"` so order isn't ambiguous in practice — Pydantic 2 calls them in declaration order; put `_no_disallowed_terms` second so the more-specific shape check runs first.

- [ ] **Step 3**: Create `apps/api/tests/services/test_content_safety.py`:

```python
def test_contains_disallowed_term_returns_false_for_clean_text(): ...
def test_contains_disallowed_term_is_case_insensitive(monkeypatch):
    # Patch the module-level pattern to compile against a known term ("foo"); assert "FOO" matches.
def test_contains_disallowed_term_uses_word_boundaries(monkeypatch):
    # Patch denylist to ("ass",); assert "asset" does NOT match (word-boundary).
def test_contains_disallowed_term_returns_false_when_denylist_empty(): ...
```

- [ ] **Step 4**: Create `apps/api/tests/schemas/test_llm.py` (or extend if it exists):

```python
def test_simple_vocab_example_rejects_disallowed_term_in_definition(monkeypatch):
    # Patch app.services.content_safety._PATTERN to match "foo".
    # Build SimpleVocabExample(token="...", definition="A foo word...", example="...");
    # assert ValidationError.

def test_simple_vocab_example_rejects_disallowed_term_in_example(monkeypatch): ...

def test_simple_vocab_example_passes_when_denylist_empty(): ...
```

- [ ] **Step 5**: Commit — `feat: add denylist content-safety validator on SimpleVocabExample`.

---

## Task 2: Enrichment service (sync — no DB)

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

## Task 3: Worker task (sync entrypoint → async coroutine via `asyncio.run`)

- [ ] **Step 1**: Create `apps/api/app/workers/content_gen.py`:

```python
from __future__ import annotations

import asyncio
import logging

from datetime import datetime, timezone

from celery import Task

from app.core.celery_app import celery_app
from app.core.db import SessionLocal
from app.services.enrichment import enrich_vocab_item
from app.services.llm import LLMClient, LLMValidationFailure
from app.services.selection import select_unenriched

logger = logging.getLogger(__name__)


@celery_app.task(name="content_gen.run_daily", bind=True, max_retries=3)
def run_daily(self: Task, batch_size: int = 25) -> dict[str, int]:
    return asyncio.run(_run_daily(batch_size))


async def _run_daily(batch_size: int) -> dict[str, int]:
    succeeded = 0
    failed = 0
    async with SessionLocal() as session:
        items = await select_unenriched(session, batch_size)
        if not items:
            return {"succeeded": 0, "failed": 0}
        llm = LLMClient()
        now = datetime.now(timezone.utc)
        for item in items:
            item.last_enrichment_attempted_at = now
            try:
                result = enrich_vocab_item(item, llm)   # sync LLM call inside async context — legal
                item.definition = result.definition
                item.example_sentence = result.example
                item.enrichment_attempts = 0           # reset on success
                succeeded += 1
            except LLMValidationFailure as e:
                item.enrichment_attempts += 1
                logger.warning(
                    "content_gen_item_failed",
                    extra={
                        "vocab_item_id": str(item.id),
                        "attempts": e.attempts,
                        "total_attempts": item.enrichment_attempts,
                    },
                )
                failed += 1
        await session.commit()
    return {"succeeded": succeeded, "failed": failed}
```

**Why `bind=True, max_retries=3`:** the harness in `LLMClient.complete` already retries validation failures up to 3 times per item. The Celery `max_retries` here covers infrastructure errors (network, DB), not LLM validation — those are caught and counted. We do **not** call `self.retry()` automatically; per-item failures are recorded in the return dict for monitoring.

**Why `asyncio.run` per task call:** Celery's default prefork pool runs each task in a child process, so creating a fresh event loop per call has no cross-task contamination and negligible overhead (~5ms vs ~3s LLM calls). The async stack is reused from `app.core.db.SessionLocal`, so no second DB engine, no second driver, no second pool to size. See [ADR-0003](../../../docs/adr/0003-celery-tasks-use-asyncio-run-not-sync-engine.md).

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

def test_run_daily_increments_attempts_on_failure(...):
    # 1 item starts at enrichment_attempts=0; LLMClient raises LLMValidationFailure;
    # assert post-state has enrichment_attempts=1 and last_enrichment_attempted_at set.

def test_run_daily_resets_attempts_on_success(...):
    # 1 item starts at enrichment_attempts=2; LLM returns valid result;
    # assert post-state has enrichment_attempts=0 and definition populated.
```

For the LLMClient monkeypatch, target `app.workers.content_gen.LLMClient` (where it's imported), not the original module. Tests call the task body directly — either invoke `run_daily.apply(kwargs={"batch_size": N})` (Celery's synchronous local-execution helper) or call `asyncio.run(_run_daily(N))` against the test DB session. Pick whichever fits the existing test pattern in `tests/conftest.py`.

- [ ] **Step 3**: Commit — `feat: add content_gen.run_daily celery task`.

---

## Task 4: Beat schedule + autodiscover

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
            # 19:00 UTC = 02:00 WIB — true overnight for the current solo user.
            # Cron is global (see ADR-0004); revisit when adding non-WIB users.
            "schedule": crontab(hour=19, minute=0),
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
    # crontab(hour=19, minute=0) — assert hour and minute fields:
    sched = entry["schedule"]
    assert 19 in sched.hour and 0 in sched.minute
```

- [ ] **Step 3**: Commit — `feat: schedule content_gen.run_daily nightly via celery beat`.

---

## Task 5: Verification + PR

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
- An item that fails enrichment 3 times is excluded from `select_unenriched` for `COOLDOWN_DAYS` (7) after its last attempt — see ADR-0005. On a successful enrichment, `enrichment_attempts` resets to 0.
- LLM outputs containing terms from the content-safety denylist fail validation; the existing retry-with-prompt-refinement loop in `LLMClient.complete` asks the model to regenerate. After 3 refinements, the item joins the cooldown queue described above. See [ADR-0007](../../../docs/adr/0007-denylist-content-safety-on-llm-output.md).

## Notes / gotchas

- **Sync entrypoint, async body.** Celery 5 tasks are sync at the entrypoint, so `run_daily` is `def`, not `async def`. The body is delegated to `_run_daily` via `asyncio.run(...)`. This pattern is repeatable: any future task should follow the same shape — sync `@celery_app.task` wrapper → `asyncio.run(_async_body(...))`. See ADR-0003.
- **`LLMClient.complete` is sync** — the existing client wraps OpenAI's sync `OpenAI` client (see `apps/api/app/services/llm.py:32`). Calling it inside an `async def` is legal; it just blocks the event loop for the duration of the HTTP call. Inside a single-coroutine task with no other awaiting work, this is fine.
- **Idempotent enrichment.** `select_unenriched` keys off `definition == ""` OR `example_sentence IS NULL`. Once a row is enriched it disappears from the selection; rerunning the task is safe.
- **Logging.** `LLMClient` already logs `llm_call` and `llm_validation_failed` (`apps/api/app/services/llm.py:51,67`). The worker logs only `content_gen_item_failed` so the per-item attempt count is preserved.
- **Inspecting failed enrichments.** `SELECT token, language, enrichment_attempts, last_enrichment_attempted_at FROM vocab_items WHERE definition='' AND enrichment_attempts >= 3 ORDER BY last_enrichment_attempted_at DESC;` lists every cooldown'd item. To force a retry, `UPDATE vocab_items SET enrichment_attempts=0 WHERE id='...';` and wait for the next nightly run.
