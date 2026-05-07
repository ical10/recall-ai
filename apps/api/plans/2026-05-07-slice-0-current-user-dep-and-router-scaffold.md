# Slice 0 — Current-user dependency + API router scaffold

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Land a small shared scaffold on `main` so the four parallel feature slices (A/B/C/D) can each drop in their own sub-router without duplicating dependencies. Adds a `get_current_user` FastAPI dependency that returns a fixed dev user (`dev@local`) until real Google OAuth lands as a separate hand-written track. Refactors `apps/api/app/main.py` to mount a single top-level `app.api.router:router`.

**Architecture:** One router scaffold (`apps/api/app/api/router.py`) aggregates feature sub-routers as they merge. One `deps.py` exposes `get_current_user` (idempotent get-or-create on the dev user) and a shared `Jinja2Templates` instance so sub-routers can render templates without re-instantiating. `main.py` includes the aggregate router; `/healthz` stays inline (it's an infra healthcheck, not a feature route). The inline `/` is removed — Slice C will register the dashboard at `/dashboard` and may add a `/` redirect.

**Tech stack:** FastAPI, SQLAlchemy 2.0 async (`get_session` already in `app/core/db.py`), pydantic v2.

---

## File Structure

**Create:**
- `apps/api/app/api/deps.py` — `get_current_user` dep + shared `templates` instance
- `apps/api/app/api/router.py` — empty `APIRouter` aggregator
- `apps/api/tests/api/__init__.py`
- `apps/api/tests/api/test_deps.py` — covers idempotency + creation behavior

**Modify:**
- `apps/api/app/main.py` — remove inline `GET /`; import and include `app.api.router:router`; move `Jinja2Templates(...)` instantiation out (or import shared one from `deps.py`)
- `apps/api/tests/test_root.py` — assertion for `GET /` is now "not found" (until Slice C registers `/`)

**No edits to:** any model, service, schema, template, or migration.

---

## Task 1: Add `get_current_user` dependency

- [ ] **Step 1**: Create `apps/api/app/api/__init__.py` if it does not exist (empty file).

- [ ] **Step 2**: Create `apps/api/app/api/deps.py`:

```python
from pathlib import Path

from fastapi import Depends
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_session
from app.models.user import User

DEV_USER_EMAIL = "dev@local"
DEV_USER_GOOGLE_ID = "dev-local"
DEV_USER_NAME = "Dev"

BASE_DIR = Path(__file__).resolve().parent.parent.parent
TEMPLATES_DIR = BASE_DIR / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))


async def get_current_user(session: AsyncSession = Depends(get_session)) -> User:
    stmt = select(User).where(User.email == DEV_USER_EMAIL)
    user = (await session.execute(stmt)).scalar_one_or_none()
    if user is not None:
        return user
    user = User(
        email=DEV_USER_EMAIL,
        google_id=DEV_USER_GOOGLE_ID,
        name=DEV_USER_NAME,
    )
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user
```

The `BASE_DIR` resolution mirrors `apps/api/app/main.py:13` (`Path(__file__).resolve().parent.parent.parent` from `app/api/deps.py` reaches `apps/api/`).

- [ ] **Step 3**: Commit — `feat: add get_current_user dev-stub dependency and shared Jinja2Templates instance`.

---

## Task 2: Add the API router scaffold

- [ ] **Step 1**: Create `apps/api/app/api/router.py`:

```python
from fastapi import APIRouter

router = APIRouter()
```

Sub-router includes (`router.include_router(...)`) will be added one line at a time by feature slices A/B/C/D when they merge.

- [ ] **Step 2**: Commit — `feat: add empty APIRouter aggregator under app.api.router`.

---

## Task 3: Refactor `main.py` to mount the aggregate router

- [ ] **Step 1**: Edit `apps/api/app/main.py`:
  - Replace the inline `Jinja2Templates(...)` line with `from app.api.deps import templates` (or just remove the local instance — Slice C will own the dashboard).
  - Remove the inline `@app.get("/")` and its template render.
  - Add `from app.api.router import router as api_router` and inside `create_app()` after the static mount: `app.include_router(api_router)`.

The resulting `create_app()` body should look like:

```python
def create_app() -> FastAPI:
    app = FastAPI(title="RecallAI", lifespan=lifespan)
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

    @app.middleware("http")
    async def add_static_cache_headers(
        request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        response = await call_next(request)
        if request.url.path.startswith("/static/") and response.status_code == 200:
            response.headers["Cache-Control"] = f"public, max-age={STATIC_CACHE_MAX_AGE}"
        return response

    @app.get("/healthz")
    async def healthz() -> JSONResponse:
        return JSONResponse({"status": "ok"})

    app.include_router(api_router)
    return app
```

- [ ] **Step 2**: Update `apps/api/tests/test_root.py` so `GET /` now expects 404 (the existing index test no longer applies until Slice C lands). Keep the file — rename the test or add a comment that Slice C re-introduces `/`. Acceptable replacement:

```python
def test_root_returns_404_until_dashboard_lands(client: TestClient) -> None:
    response = client.get("/")
    assert response.status_code == 404
```

- [ ] **Step 3**: Commit — `refactor: mount app.api.router and remove inline GET / route`.

---

## Task 4: Tests for `get_current_user`

- [ ] **Step 1**: Create `apps/api/tests/api/__init__.py` (empty).

- [ ] **Step 2**: Create `apps/api/tests/api/test_deps.py`:

```python
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.api.deps import DEV_USER_EMAIL, get_current_user
from app.core.db import get_session
from app.models.user import User


@pytest.fixture
def app_with_probe() -> FastAPI:
    app = FastAPI()

    @app.get("/_probe")
    async def probe(user: User = Depends(get_current_user)) -> dict[str, str]:
        return {"id": str(user.id), "email": user.email}

    return app


def test_get_current_user_creates_dev_user_when_absent(client: TestClient, ...) -> None:
    # Hit a probe route that depends on get_current_user; assert a User row with email=DEV_USER_EMAIL exists.
    ...


def test_get_current_user_is_idempotent(client: TestClient, ...) -> None:
    # Hit the probe twice; assert exactly one User row with email=DEV_USER_EMAIL.
    ...


def test_get_current_user_returns_existing_row_when_present(client: TestClient, ...) -> None:
    # Pre-insert a User with email=DEV_USER_EMAIL; assert get_current_user returns its id (no duplicate created).
    ...
```

The exact fixture wiring depends on `apps/api/tests/conftest.py` and how it sets up the async session. **Read `conftest.py` first** and reuse its session/transaction fixture. The test module must override the FastAPI `get_session` dep to use the test session, the same way existing tests do. If `conftest.py` doesn't already provide a way to mount a custom probe app against the test session, add one in `tests/api/conftest.py` (do not modify the project-wide conftest).

- [ ] **Step 3**: Commit — `test: cover get_current_user dev-stub idempotency and creation`.

---

## Task 5: Verification + final commit

- [ ] **Step 1**: Run targeted tests:
```
uv run pytest apps/api/tests/api/test_deps.py apps/api/tests/test_root.py apps/api/tests/test_health.py -v
```

- [ ] **Step 2**: Run full lint:
```
pnpm lint
```

- [ ] **Step 3**: Smoke test:
```
pnpm dev
curl -s http://localhost:8000/healthz       # → {"status":"ok"}
curl -s -o /dev/null -w '%{http_code}\n' http://localhost:8000/   # → 404
```

- [ ] **Step 4**: Open PR titled `feat: current-user dev stub + API router scaffold (Slice 0)`. Squash-merge after review.

---

## Acceptance criteria

- `GET /healthz` still returns 200.
- `GET /` returns 404 (transitional — Slice C re-introduces it).
- `from app.api.deps import get_current_user, templates` works in any future router file.
- `from app.api.router import router as api_router` works in `main.py`.
- A second call to `get_current_user` does not create a duplicate `User` row (`select count(*) from users where email='dev@local'` is `1`).
- Full test suite green; ruff + mypy clean.

## Notes / gotchas

- **Auth replacement seam.** When the manual auth track lands, `get_current_user` is the only function that needs to change — sub-routers depend on it by reference. Keep this dep narrow: do not expand its return type or add side effects.
- **Templates instance.** Sub-routers should `from app.api.deps import templates` rather than instantiating their own. This keeps Jinja config (autoescape, loaders) consistent.
- **`tests/test_root.py`.** Don't delete the file — rename the test so it stays as a regression marker. Slice C will rewrite it when `/` becomes the dashboard.
- **No model/migration changes.** The `dev@local` user is created lazily on first request, not via a seed migration. Keeping migrations clean of seed data avoids prod accidentally creating dev users.
