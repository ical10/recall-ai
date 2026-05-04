# Switch LLM Provider to OpenRouter (via OpenAI SDK) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the (declared but uninstalled) Anthropic SDK choice with the OpenAI Python SDK pointed at OpenRouter, so we can use `:free` models in dev and any paid model in prod by changing one env var.

**Architecture:** Settings gain three knobs — `openrouter_api_key` (replaces `anthropic_api_key`), `openrouter_base_url` (defaults to `https://openrouter.ai/api/v1`), and `llm_model` (defaults to `meta-llama/llama-3.3-70b-instruct:free`). The `openai` package becomes a runtime dep. No client code is written in this plan; the actual LLM call sites land in a future "LLM enrichment service" plan. CLAUDE.md is updated to reflect the new stack, the new env list, and a fresh architecture-decision entry that supersedes the Anthropic one.

**Tech Stack:** OpenAI Python SDK ≥ 1.50 (drop-in client for OpenRouter's OpenAI-compatible API), pydantic-settings v2, pytest.

---

## File Structure

**Modify:**
- `pyproject.toml` — add `openai>=1.50` to `[project].dependencies`
- `apps/api/app/core/config.py` — drop `anthropic_api_key`, add `openrouter_api_key` (required), `llm_model` (default = free Llama 3.3 70B), `openrouter_base_url` (default = OpenRouter v1)
- `apps/api/tests/core/test_config.py` — update happy-path + missing-required tests for the new field set; assert defaults for `llm_model` and `openrouter_base_url`
- `apps/api/tests/conftest.py` — replace `os.environ.setdefault("ANTHROPIC_API_KEY", ...)` with `OPENROUTER_API_KEY`
- `.env.example` (repo root) — swap `ANTHROPIC_API_KEY` → `OPENROUTER_API_KEY`; add `LLM_MODEL` and `OPENROUTER_BASE_URL` lines (commented defaults)
- `apps/api/.env.example` — same as root (keep them in sync)
- `CLAUDE.md` — three changes: stack line ("anthropic sdk" → "openai sdk via openrouter"), env-var list under `## run / deploy`, and a new architecture-decision entry under `## architecture decisions`
- `.claude/agents/coder.md`, `.claude/agents/ops.md`, `.claude/agents/tester.md` — replace stale Anthropic-specific guidance with OpenAI-SDK-via-OpenRouter equivalents

**Out of scope (deliberate):**
- Writing the actual LLM client / enrichment service code — separate plan
- Pydantic schemas for LLM output validation — separate plan
- Retry-with-prompt-refinement loop — separate plan
- Mock-LLM test fixtures — separate plan
- Removing the historical `apps/api/plans/2026-05-04-scaffold-fastapi-entry.md` references to Anthropic — that plan is a frozen record and should not be retroactively edited

---

## Task 1: Add `openai` runtime dep

**Files:**
- Modify: `pyproject.toml`

- [ ] **Step 1: Add `"openai>=1.50",` to the `[project].dependencies` array**

Insert it as the first dependency (alphabetically `openai` falls between `jinja2` and `pydantic-settings`, but the existing array isn't strictly alphabetised — just append it after `httpx`):

```toml
dependencies = [
    "fastapi>=0.115",
    "uvicorn[standard]>=0.32",
    "pydantic>=2.9",
    "pydantic-settings>=2.6",
    "sqlalchemy[asyncio]>=2.0",
    "asyncpg>=0.30",
    "celery[redis]>=5.4",
    "jinja2>=3.1",
    "httpx>=0.27",
    "openai>=1.50",
]
```

- [ ] **Step 2: Sync**

Run: `uv sync`
Expected: resolves without error, installs `openai` and its transitive deps.

- [ ] **Step 3: Sanity-check the import**

Run: `uv run python -c "from openai import OpenAI; print('ok')"`
Expected: prints `ok`.

- [ ] **Step 4: Commit**

```bash
git add pyproject.toml uv.lock
git commit -m "chore: add openai sdk for OpenRouter-backed LLM calls"
```

---

## Task 2: Update Settings (TDD)

**Files:**
- Modify: `apps/api/app/core/config.py`
- Modify: `apps/api/tests/core/test_config.py`

- [ ] **Step 1: Rewrite the test file to drive the new field set**

Replace `apps/api/tests/core/test_config.py` with EXACTLY:

```python
import pytest
from pydantic import ValidationError

from app.core.config import Settings


def test_settings_loads_required_fields_from_env(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://u:p@h/d")
    monkeypatch.setenv("REDIS_URL", "redis://h:6379/0")
    monkeypatch.setenv("OPENROUTER_API_KEY", "k")
    monkeypatch.setenv("SECRET_KEY", "s")
    monkeypatch.delenv("LLM_MODEL", raising=False)
    monkeypatch.delenv("OPENROUTER_BASE_URL", raising=False)
    monkeypatch.delenv("GOOGLE_CLIENT_ID", raising=False)
    monkeypatch.delenv("GOOGLE_CLIENT_SECRET", raising=False)

    settings = Settings(_env_file=None)

    assert settings.database_url == "postgresql+asyncpg://u:p@h/d"
    assert settings.redis_url == "redis://h:6379/0"
    assert settings.openrouter_api_key == "k"
    assert settings.secret_key == "s"
    assert settings.llm_model == "meta-llama/llama-3.3-70b-instruct:free"
    assert settings.openrouter_base_url == "https://openrouter.ai/api/v1"
    assert settings.google_client_id == ""
    assert settings.google_client_secret == ""


def test_settings_overrides_llm_defaults_from_env(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://u:p@h/d")
    monkeypatch.setenv("REDIS_URL", "redis://h:6379/0")
    monkeypatch.setenv("OPENROUTER_API_KEY", "k")
    monkeypatch.setenv("SECRET_KEY", "s")
    monkeypatch.setenv("LLM_MODEL", "openai/gpt-4o-mini")
    monkeypatch.setenv("OPENROUTER_BASE_URL", "https://example.test/v1")

    settings = Settings(_env_file=None)

    assert settings.llm_model == "openai/gpt-4o-mini"
    assert settings.openrouter_base_url == "https://example.test/v1"


def test_settings_missing_required_raises(monkeypatch):
    for key in ("DATABASE_URL", "REDIS_URL", "OPENROUTER_API_KEY", "SECRET_KEY"):
        monkeypatch.delenv(key, raising=False)

    with pytest.raises(ValidationError):
        Settings(_env_file=None)
```

- [ ] **Step 2: Run the tests — they MUST fail**

Run: `uv run pytest apps/api/tests/core/test_config.py -v`
Expected: failures from `AttributeError: 'Settings' object has no attribute 'openrouter_api_key'` (or similar) — proving the implementation hasn't caught up yet.

- [ ] **Step 3: Update `apps/api/app/core/config.py` to EXACTLY:**

```python
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str
    redis_url: str
    openrouter_api_key: str
    secret_key: str
    llm_model: str = "meta-llama/llama-3.3-70b-instruct:free"
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    google_client_id: str = ""
    google_client_secret: str = ""


@lru_cache
def get_settings() -> Settings:
    return Settings()
```

- [ ] **Step 4: Update `apps/api/tests/conftest.py`** — replace the `ANTHROPIC_API_KEY` line with `OPENROUTER_API_KEY`. New file content (only line 6 changes):

```python
import os
from collections.abc import Iterator

os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://test:test@localhost:5432/test")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("OPENROUTER_API_KEY", "test-key")
os.environ.setdefault("SECRET_KEY", "test-secret")

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client() -> Iterator[TestClient]:
    from app.main import app

    with TestClient(app) as test_client:
        yield test_client
```

- [ ] **Step 5: Run the full suite — everything must pass**

Run: `uv run pytest -v`
Expected: 10 passed (was 9; adds the new `test_settings_overrides_llm_defaults_from_env`). The other 7 tests must still pass — the conftest swap is what keeps them green.

- [ ] **Step 6: Commit**

```bash
git add apps/api/app/core/config.py apps/api/tests/core/test_config.py apps/api/tests/conftest.py
git commit -m "feat: switch Settings from anthropic to openrouter LLM provider"
```

---

## Task 3: Update `.env.example` files

**Files:**
- Modify: `.env.example` (repo root)
- Modify: `apps/api/.env.example`

- [ ] **Step 1: Overwrite `/Users/rizal/GDrive/recall-ai/.env.example` with EXACTLY:**

```env
DATABASE_URL=postgresql+asyncpg://user:password@localhost:5432/recallai
REDIS_URL=redis://localhost:6379/0
OPENROUTER_API_KEY=sk-or-v1-...
# Optional — defaults to a free OpenRouter model; override for prod
# LLM_MODEL=meta-llama/llama-3.3-70b-instruct:free
# OPENROUTER_BASE_URL=https://openrouter.ai/api/v1
GOOGLE_CLIENT_ID=
GOOGLE_CLIENT_SECRET=
SECRET_KEY=change-me-in-production
```

- [ ] **Step 2: Overwrite `/Users/rizal/GDrive/recall-ai/apps/api/.env.example` with the SAME content** (keep them in sync byte-for-byte).

- [ ] **Step 3: Commit**

```bash
git add .env.example apps/api/.env.example
git commit -m "docs: swap ANTHROPIC_API_KEY for OPENROUTER_API_KEY in .env.example"
```

---

## Task 4: Update CLAUDE.md

**Files:**
- Modify: `CLAUDE.md`

Three precise edits — do not touch other sections.

- [ ] **Step 1: Update the stack line.** Find:

```
- stack: python 3.11, fastapi, htmx, jinja2, tailwind css, postgres via sqlalchemy 2.0 (async), redis, celery 5, pydantic v2, anthropic sdk
```

Replace `anthropic sdk` with `openai sdk (via openrouter)`. Result:

```
- stack: python 3.11, fastapi, htmx, jinja2, tailwind css, postgres via sqlalchemy 2.0 (async), redis, celery 5, pydantic v2, openai sdk (via openrouter)
```

- [ ] **Step 2: Update the env-var list under `## run / deploy`.** Find the bullet:

```
- env vars (`DATABASE_URL`, `REDIS_URL`, `ANTHROPIC_API_KEY`, `SECRET_KEY`, `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`) come from railway env / shared variables.
```

Replace `ANTHROPIC_API_KEY` with `OPENROUTER_API_KEY` and add `LLM_MODEL`, `OPENROUTER_BASE_URL` as optional follow-ups in the same bullet:

```
- required env vars: `DATABASE_URL`, `REDIS_URL`, `OPENROUTER_API_KEY`, `SECRET_KEY`, `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`. optional: `LLM_MODEL` (defaults to a free OpenRouter model — override per environment, e.g. prod = `openai/gpt-4o-mini`), `OPENROUTER_BASE_URL` (defaults to `https://openrouter.ai/api/v1`). all come from railway env / shared variables. railway's postgres + redis addons inject `DATABASE_URL` and `REDIS_URL` automatically when attached.
```

- [ ] **Step 3: Replace the architecture-decision entry.** Find:

```
- chose anthropic claude over openai (may 2026): tighter instruction-following on short factual content during early prototyping
```

Replace with (note the new date 2026-05-04 reflecting today, and supersede language):

```
- chose openai sdk targeting openrouter over anthropic sdk (2026-05-04, supersedes earlier may-2026 anthropic call): openrouter is openai-api-compatible so the openai python sdk works as the client; gives access to `:free` models for dev/staging while letting prod swap to any paid model (openai, anthropic, google) by changing the `LLM_MODEL` env var with no code change. dev defaults to `meta-llama/llama-3.3-70b-instruct:free`; prod should pick a paid model with reliable structured-output support. retry-with-prompt-refinement loop already planned absorbs the lower instruction-following quality of free models.
```

- [ ] **Step 4: Commit**

```bash
git add CLAUDE.md
git commit -m "docs: update CLAUDE.md for openai-sdk-via-openrouter switch"
```

---

## Task 5: Update Claude Code agent configs

**Files:**
- Modify: `.claude/agents/coder.md`
- Modify: `.claude/agents/ops.md`
- Modify: `.claude/agents/tester.md`

These are personal Claude Code agent configs. They contain stale Anthropic-specific guidance that future agent invocations will read. Updating them avoids confusing instructions.

- [ ] **Step 1: In `.claude/agents/coder.md`**, find:

```
- Always include: timeout (httpx or anthropic sdk timeout), retry decorator, token cost logging
```

Replace with:

```
- Always include: timeout (httpx or openai sdk `timeout=` kwarg), retry decorator, token cost logging
```

- [ ] **Step 2: In `.claude/agents/ops.md`**, find:

```
- `ANTHROPIC_API_KEY` — Claude API key
```

Replace with:

```
- `OPENROUTER_API_KEY` — OpenRouter API key (used via OpenAI SDK; format `sk-or-v1-...`)
- `LLM_MODEL` — optional, defaults to a free OpenRouter model
- `OPENROUTER_BASE_URL` — optional, defaults to `https://openrouter.ai/api/v1`
```

- [ ] **Step 3: In `.claude/agents/tester.md`**, find:

```
- Mock LLM calls (Anthropic SDK) in all unit tests — never make real API calls in the test suite
```

Replace with:

```
- Mock LLM calls (OpenAI SDK pointed at OpenRouter) in all unit tests — never make real API calls in the test suite
```

- [ ] **Step 4: Commit**

```bash
git add .claude/agents/coder.md .claude/agents/ops.md .claude/agents/tester.md
git commit -m "chore: update local agent configs for openrouter switch"
```

---

## Task 6: Final verification

- [ ] **Step 1: Run the full test suite**

Run: `uv run pytest -v`
Expected: 10 passed.

- [ ] **Step 2: Run lint + types**

Run: `pnpm lint`
Expected: ruff check pass, ruff format check pass, mypy strict pass.

- [ ] **Step 3: Smoke-test dev with the new env**

```bash
cd /Users/rizal/GDrive/recall-ai
cp .env.example .env
# .env now has OPENROUTER_API_KEY=sk-or-v1-... placeholder which is non-empty, so Settings() loads
pnpm start &
SERVER_PID=$!
sleep 3
curl -s http://localhost:8000/healthz
echo
kill $SERVER_PID 2>/dev/null
wait $SERVER_PID 2>/dev/null
rm .env
```

Expected: `{"status":"ok"}` printed.

- [ ] **Step 4: Confirm no stale `anthropic` references remain in live code**

Run: `grep -rin "anthropic" /Users/rizal/GDrive/recall-ai --include="*.py" --include="*.toml" --include="*.json" --include="*.example" 2>/dev/null | grep -v ".venv" | grep -v ".git/" | grep -v "node_modules" | grep -v "plans/2026-05-04-scaffold-fastapi-entry.md"`
Expected: empty output. (The historical scaffold plan is allowed to keep its references — it's a frozen record.)

No commit for verification — if anything fails here, go back and fix.

---

## Risks

- **Free models have weaker instruction-following.** `meta-llama/llama-3.3-70b-instruct:free` is the strongest current free option; the planned pydantic-validator-with-retry pipeline absorbs the failure modes. Track validation failure rate per model once enrichment lands.
- **Free-tier rate limits** (typically ~50–1000 req/day depending on credit balance) will cap the daily content generation pipeline. Confirm scale before relying on free in prod.
- **`response_format` reliability varies per model on OpenRouter.** Pydantic validation at the schema boundary is already the mitigation per CLAUDE.md.
- **Architecture-decision supersession.** The new entry references the old one; both stay in CLAUDE.md so the history is preserved.
