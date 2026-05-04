# Scaffold FastAPI Entry Point Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stand up a runnable FastAPI app at `apps/api/app/main.py` with typed settings, an async SQLAlchemy session factory, a Celery app bound to Redis, and a Jinja2 base template wired for HTMX + Tailwind — verified end-to-end by a passing test suite.

**Architecture:** Single FastAPI process exposes `/healthz` (JSON) and `/` (HTML). Settings come from a Pydantic `BaseSettings` class loaded from environment variables; the SQLAlchemy async engine and Celery app are constructed once at import time using those settings. Templates live under `apps/api/templates/` with a `base.html` that loads HTMX 2.x and the Tailwind Play CDN; the index page extends it. No auth, no DB models, no Celery tasks yet — those land in later plans.

**Tech Stack:** Python 3.11, FastAPI, Starlette `Jinja2Templates`, SQLAlchemy 2.0 async + asyncpg, Celery 5 + redis broker, pydantic-settings v2, HTMX 2.0.4, Tailwind Play CDN. Tests use `fastapi.testclient.TestClient` (httpx-backed, sync).

---

## File Structure

**Create:**
- `apps/api/app/core/config.py` — typed `Settings` class + cached `get_settings()`
- `apps/api/app/core/db.py` — async engine, `async_sessionmaker`, `get_session` dep
- `apps/api/app/core/celery_app.py` — `celery_app` instance bound to Redis
- `apps/api/app/main.py` — FastAPI app factory, lifespan, `/healthz`, `/`, static mount
- `apps/api/templates/base.html` — base layout with HTMX + Tailwind CDN
- `apps/api/templates/pages/index.html` — minimal landing page
- `apps/api/tests/conftest.py` — env defaults + `client` fixture
- `apps/api/tests/core/__init__.py` — package marker
- `apps/api/tests/core/test_config.py` — Settings happy-path + missing-env failure
- `apps/api/tests/core/test_db.py` — engine URL + sessionmaker class
- `apps/api/tests/core/test_celery_app.py` — broker + backend config
- `apps/api/tests/test_health.py` — `/healthz` returns 200 JSON
- `apps/api/tests/test_root.py` — `/` renders HTML containing HTMX + Tailwind tags

**Modify:**
- `pyproject.toml` — add runtime deps; widen `testpaths` is already correct

**No edits to:** `.claude/`, `.gitignore`, `alembic/`, existing empty `__init__.py` files.

**Boundaries:** `core/config.py` is the only place that reads env. `core/db.py` and `core/celery_app.py` only depend on `core/config.py`. `main.py` depends on `core/*` and `templates/`. Templates depend on nothing.

---

## Task 1: Add runtime dependencies

**Files:**
- Modify: `/Users/rizal/GDrive/recall-ai/pyproject.toml`

- [ ] **Step 1: Edit `pyproject.toml` to add runtime + test deps**

Replace the file contents with:

```toml
[project]
name = "recall-ai"
version = "0.1.0"
description = "Spaced-repetition vocabulary trainer for ESL learners."
requires-python = ">=3.11,<3.12"
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
]

[dependency-groups]
dev = [
    "pytest>=8",
    "tdd-guard-pytest>=0.1",
]

[tool.pytest.ini_options]
tdd_guard_project_root = "/Users/rizal/GDrive/recall-ai"
testpaths = ["apps/api/tests"]
pythonpath = ["apps/api"]
```

Note `pythonpath = ["apps/api"]` — this lets test files do `from app.core.config import Settings` without a package install.

- [ ] **Step 2: Sync the environment**

Run: `uv sync`
Expected: resolves and installs fastapi, uvicorn, pydantic-settings, sqlalchemy, asyncpg, celery, redis client, jinja2, httpx alongside existing pytest + tdd-guard-pytest. No errors.

- [ ] **Step 3: Sanity check imports**

Run: `uv run python -c "import fastapi, sqlalchemy, celery, jinja2, pydantic_settings, asyncpg, httpx; print('ok')"`
Expected: prints `ok`.

- [ ] **Step 4: Commit**

```bash
git add pyproject.toml uv.lock
git commit -m "chore: add fastapi, sqlalchemy async, celery, jinja2 runtime deps"
```

---

## Task 2: Test scaffolding (conftest + core package marker)

**Files:**
- Create: `apps/api/tests/conftest.py`
- Create: `apps/api/tests/core/__init__.py`

- [ ] **Step 1: Create `apps/api/tests/core/__init__.py`**

Empty file:

```python
```

- [ ] **Step 2: Create `apps/api/tests/conftest.py`**

```python
import os
from collections.abc import Iterator

os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://test:test@localhost:5432/test")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("ANTHROPIC_API_KEY", "test-key")
os.environ.setdefault("SECRET_KEY", "test-secret")

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client() -> Iterator[TestClient]:
    from app.main import app

    with TestClient(app) as test_client:
        yield test_client
```

The `os.environ.setdefault` calls run before any `app.*` import, so `Settings()` sees a populated env when modules at import time call `get_settings()`.

- [ ] **Step 3: Verify pytest still collects (no tests yet, no errors)**

Run: `uv run pytest -q`
Expected: `no tests ran` or similar — the key is no import errors.

- [ ] **Step 4: Commit**

```bash
git add apps/api/tests/conftest.py apps/api/tests/core/__init__.py
git commit -m "test: add pytest conftest with env defaults and client fixture"
```

---

## Task 3: Settings (`app/core/config.py`)

**Files:**
- Create: `apps/api/app/core/config.py`
- Test: `apps/api/tests/core/test_config.py`

- [ ] **Step 1: Write the failing tests**

Create `apps/api/tests/core/test_config.py`:

```python
import pytest
from pydantic import ValidationError

from app.core.config import Settings


def test_settings_loads_required_fields_from_env(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://u:p@h/d")
    monkeypatch.setenv("REDIS_URL", "redis://h:6379/0")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "k")
    monkeypatch.setenv("SECRET_KEY", "s")
    monkeypatch.delenv("GOOGLE_CLIENT_ID", raising=False)
    monkeypatch.delenv("GOOGLE_CLIENT_SECRET", raising=False)

    settings = Settings(_env_file=None)

    assert settings.database_url == "postgresql+asyncpg://u:p@h/d"
    assert settings.redis_url == "redis://h:6379/0"
    assert settings.anthropic_api_key == "k"
    assert settings.secret_key == "s"
    assert settings.google_client_id == ""
    assert settings.google_client_secret == ""


def test_settings_missing_required_raises(monkeypatch):
    for key in ("DATABASE_URL", "REDIS_URL", "ANTHROPIC_API_KEY", "SECRET_KEY"):
        monkeypatch.delenv(key, raising=False)

    with pytest.raises(ValidationError):
        Settings(_env_file=None)
```

- [ ] **Step 2: Run the tests — they must fail**

Run: `uv run pytest apps/api/tests/core/test_config.py -v`
Expected: collection or import error — `ModuleNotFoundError: No module named 'app.core.config'` (or similar).

- [ ] **Step 3: Implement `apps/api/app/core/config.py`**

```python
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str
    redis_url: str
    anthropic_api_key: str
    secret_key: str
    google_client_id: str = ""
    google_client_secret: str = ""


@lru_cache
def get_settings() -> Settings:
    return Settings()
```

- [ ] **Step 4: Run the tests — they must pass**

Run: `uv run pytest apps/api/tests/core/test_config.py -v`
Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add apps/api/app/core/config.py apps/api/tests/core/test_config.py
git commit -m "feat: add typed Settings loaded from environment"
```

---

## Task 4: Async DB session (`app/core/db.py`)

**Files:**
- Create: `apps/api/app/core/db.py`
- Test: `apps/api/tests/core/test_db.py`

- [ ] **Step 1: Write the failing tests**

Create `apps/api/tests/core/test_db.py`:

```python
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from app.core.db import SessionLocal, engine


def test_engine_is_async_and_uses_asyncpg():
    assert isinstance(engine, AsyncEngine)
    assert "asyncpg" in str(engine.url)


def test_sessionmaker_yields_async_sessions():
    assert isinstance(SessionLocal, async_sessionmaker)
    assert SessionLocal.class_ is AsyncSession
```

- [ ] **Step 2: Run the tests — they must fail**

Run: `uv run pytest apps/api/tests/core/test_db.py -v`
Expected: `ModuleNotFoundError: No module named 'app.core.db'`.

- [ ] **Step 3: Implement `apps/api/app/core/db.py`**

```python
from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import get_settings

engine: AsyncEngine = create_async_engine(
    get_settings().database_url,
    echo=False,
    future=True,
)

SessionLocal = async_sessionmaker(engine, expire_on_commit=False)


async def get_session() -> AsyncIterator[AsyncSession]:
    async with SessionLocal() as session:
        yield session
```

- [ ] **Step 4: Run the tests — they must pass**

Run: `uv run pytest apps/api/tests/core/test_db.py -v`
Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add apps/api/app/core/db.py apps/api/tests/core/test_db.py
git commit -m "feat: add async SQLAlchemy engine and session factory"
```

---

## Task 5: Celery app (`app/core/celery_app.py`)

**Files:**
- Create: `apps/api/app/core/celery_app.py`
- Test: `apps/api/tests/core/test_celery_app.py`

- [ ] **Step 1: Write the failing tests**

Create `apps/api/tests/core/test_celery_app.py`:

```python
from celery import Celery

from app.core.celery_app import celery_app


def test_celery_app_is_celery_instance():
    assert isinstance(celery_app, Celery)


def test_celery_app_uses_redis_broker_and_backend():
    assert celery_app.conf.broker_url.startswith("redis://")
    assert celery_app.conf.result_backend.startswith("redis://")


def test_celery_app_uses_json_serialization_and_utc():
    assert celery_app.conf.task_serializer == "json"
    assert celery_app.conf.result_serializer == "json"
    assert celery_app.conf.accept_content == ["json"]
    assert celery_app.conf.timezone == "UTC"
    assert celery_app.conf.enable_utc is True
```

- [ ] **Step 2: Run the tests — they must fail**

Run: `uv run pytest apps/api/tests/core/test_celery_app.py -v`
Expected: `ModuleNotFoundError: No module named 'app.core.celery_app'`.

- [ ] **Step 3: Implement `apps/api/app/core/celery_app.py`**

```python
from celery import Celery

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
)
```

- [ ] **Step 4: Run the tests — they must pass**

Run: `uv run pytest apps/api/tests/core/test_celery_app.py -v`
Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add apps/api/app/core/celery_app.py apps/api/tests/core/test_celery_app.py
git commit -m "feat: add Celery app bound to Redis broker and backend"
```

---

## Task 6: Base template + index page

**Files:**
- Create: `apps/api/templates/base.html`
- Create: `apps/api/templates/pages/index.html`

(Templates are exercised by Task 7's tests — no separate test file.)

- [ ] **Step 1: Create `apps/api/templates/base.html`**

```html
<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>{% block title %}RecallAI{% endblock %}</title>
    <script src="https://unpkg.com/htmx.org@2.0.4"></script>
    <script src="https://cdn.tailwindcss.com"></script>
  </head>
  <body class="min-h-screen bg-gray-50 text-gray-900 antialiased">
    {% block content %}{% endblock %}
  </body>
</html>
```

- [ ] **Step 2: Create `apps/api/templates/pages/index.html`**

```html
{% extends "base.html" %}
{% block content %}
<main class="mx-auto max-w-2xl p-8">
  <h1 class="text-3xl font-semibold">RecallAI</h1>
  <p class="mt-2 text-gray-600">Spaced-repetition vocabulary trainer.</p>
</main>
{% endblock %}
```

- [ ] **Step 3: Commit**

```bash
git add apps/api/templates/base.html apps/api/templates/pages/index.html
git commit -m "feat: add base Jinja2 template with HTMX and Tailwind CDN"
```

---

## Task 7: FastAPI entry point (`app/main.py`)

**Files:**
- Create: `apps/api/app/main.py`
- Test: `apps/api/tests/test_health.py`
- Test: `apps/api/tests/test_root.py`

- [ ] **Step 1: Write the failing health test**

Create `apps/api/tests/test_health.py`:

```python
def test_healthz_returns_ok(client):
    response = client.get("/healthz")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
```

- [ ] **Step 2: Write the failing root test**

Create `apps/api/tests/test_root.py`:

```python
def test_index_renders_with_htmx_and_tailwind(client):
    response = client.get("/")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")

    body = response.text
    assert "RecallAI" in body
    assert "htmx.org" in body
    assert "tailwindcss" in body
```

- [ ] **Step 3: Run both tests — they must fail**

Run: `uv run pytest apps/api/tests/test_health.py apps/api/tests/test_root.py -v`
Expected: collection error — `ModuleNotFoundError: No module named 'app.main'` (the `client` fixture imports `app.main`).

- [ ] **Step 4: Implement `apps/api/app/main.py`**

```python
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.core.db import engine

BASE_DIR = Path(__file__).resolve().parent.parent
TEMPLATES_DIR = BASE_DIR / "templates"
STATIC_DIR = BASE_DIR / "static"

templates = Jinja2Templates(directory=str(TEMPLATES_DIR))


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    yield
    await engine.dispose()


def create_app() -> FastAPI:
    app = FastAPI(title="RecallAI", lifespan=lifespan)
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

    @app.get("/healthz")
    async def healthz() -> JSONResponse:
        return JSONResponse({"status": "ok"})

    @app.get("/")
    async def index(request: Request) -> Response:
        return templates.TemplateResponse(request, "pages/index.html")

    return app


app = create_app()
```

- [ ] **Step 5: Run both tests — they must pass**

Run: `uv run pytest apps/api/tests/test_health.py apps/api/tests/test_root.py -v`
Expected: 2 passed.

- [ ] **Step 6: Run the full suite to confirm nothing regressed**

Run: `uv run pytest -v`
Expected: 9 passed (2 config + 2 db + 3 celery + 1 health + 1 root).

- [ ] **Step 7: Boot the server manually as a smoke check**

Run: `uv run uvicorn app.main:app --app-dir apps/api --port 8000` and hit `http://localhost:8000/` and `http://localhost:8000/healthz` in a browser.
Expected: index page renders with the RecallAI heading; `/healthz` returns `{"status":"ok"}`. Stop with Ctrl-C.

(This step requires `DATABASE_URL` etc. to be set in the shell or in `apps/api/.env` — copy `.env.example` to `.env` first, or export the four required vars. Connection isn't actually opened on startup, so localhost-only `DATABASE_URL` placeholders are fine.)

- [ ] **Step 8: Commit**

```bash
git add apps/api/app/main.py apps/api/tests/test_health.py apps/api/tests/test_root.py
git commit -m "feat: add FastAPI app with /healthz and / index route"
```

---

## Out of Scope (Deliberate)

- Google OAuth wiring (per CLAUDE.md, hand-written; separate plan)
- SQLAlchemy ORM models, Alembic env.py, first migration
- Celery beat schedule + first task
- HTMX partial routes, review flow, dashboard
- Tailwind production build (CDN is fine for development per CLAUDE.md)
- Ruff + mypy config (separate plan once first non-scaffold code lands)
- Deployment config (Railway service definitions)

## Risks

- **pydantic-settings reading `.env` during tests** — mitigated by passing `_env_file=None` in test_config.py and by `monkeypatch.setenv` in conftest. If a stray `.env` file is present in the working dir at test time, the happy-path test could pick up unintended values. Tests use direct `Settings(_env_file=None)` to avoid this.
- **`get_settings()` cache pollution across tests** — config tests bypass the cached helper. DB and Celery modules are imported once and freeze their config at import time, which is fine for this scaffold but will need rethinking if we add tests that swap settings on the fly.
- **Tailwind Play CDN warns in production** — acceptable for now; CLAUDE.md flags compile-before-deploy, which is its own future task.

## Open Questions (default chosen, flag if you disagree)

- **Pythonpath strategy:** `pyproject.toml` sets `pythonpath = ["apps/api"]` so `from app.core...` works without packaging. Alternative: make `apps/api` an installable package via `[tool.uv.workspace]`. Defaulted to the simpler pythonpath approach for the scaffold.
- **Engine constructed at import time:** `core/db.py` builds `engine` at module load. This is conventional for FastAPI apps but means tests for `db.py` execute against the env that conftest sets. If you'd prefer a lazy factory (`get_engine()`), say so before Task 4.
