# CLAUDE.md

## project
- name: RecallAI
- stack: python 3.11, fastapi, htmx, jinja2, tailwind css, postgres via sqlalchemy 2.0 (async), redis, celery 5, pydantic v2, openai sdk (via openrouter)
- deployed on railway: web service + celery worker + celery beat + postgres addon + redis addon
- monorepo managed with pnpm workspaces + turborepo
- domain: spaced-repetition vocabulary trainer with llm-generated content for esl learners
- solo project — no team, no staging branch, main only

## folder structure
```
/                             ← monorepo root (pnpm workspaces + turborepo)
  /apps/
    /api/                     ← fastapi application
      /app/
        /api/                 ← route handlers (async def only)
        /core/                ← config, db engine, celery app, logging
        /models/              ← sqlalchemy 2.0 orm models
        /schemas/             ← pydantic v2 schemas (request, response, llm output)
        /services/            ← business logic layer
        /workers/             ← celery task definitions (sync def only)
      /templates/             ← jinja2 html templates
        /base.html            ← base layout with htmx + tailwind cdn
        /partials/            ← htmx partial responses (card, rating, stats)
        /pages/               ← full page templates (dashboard, review, settings)
      /static/
        /css/                 ← compiled tailwind output (if not using cdn)
        /js/                  ← minimal custom js only — prefer htmx attributes
      /alembic/               ← migrations (one per logical change)
      /tests/                 ← mirrors /app structure, named test_*.py
      /plans/                 ← pre-coding plan documents (required for 3+ file tasks)
  /packages/
    /shared/                  ← shared constants, enums, api contract types (if needed)
```

## auth
- google oauth (credentials provided by developer at session start — never hardcode or commit)
- all auth-related code must be written by hand — ai-generated auth logic is not accepted as-is
- user data access must be audited manually before any PR is considered complete

## run / deploy
- `.env` lives at the repo root (copied from `.env.example`); `pydantic-settings` reads it relative to the CWD where uvicorn runs, which is the repo root.
- dev: `pnpm dev` → `uv run uvicorn app.main:app --app-dir apps/api --reload --port 8000`. server-rendered htmx + jinja2 + tailwind cdn means there is no separate "frontend" — the FastAPI app *is* the frontend. open http://localhost:8000.
- prod (local sanity): `pnpm start` → same command, no `--reload`, binds `0.0.0.0:$PORT` (defaults to 8000).
- celery worker (local or railway): `pnpm worker` → `uv run --project . celery -A app.core.celery_app:celery_app --workdir apps/api worker --loglevel=info`.
- celery beat (local or railway): `pnpm beat` → same with `beat` instead of `worker`.
- tests: `pnpm test` (full suite) or `uv run pytest <path>` for a single file.
- lint + types: `pnpm lint` runs ruff check + ruff format check + mypy strict on `apps/api/app`.

### railway
- one repo, three services. each service points at this repo and overrides the start command in the railway dashboard:
  - **web**: leave default — `railway.json` already specifies the uvicorn command + `/healthz` healthcheck.
  - **worker**: start command `uv run --project . celery -A app.core.celery_app:celery_app --workdir apps/api worker --loglevel=info`
  - **beat**: start command `uv run --project . celery -A app.core.celery_app:celery_app --workdir apps/api beat --loglevel=info`
- nixpacks build is configured in `nixpacks.toml`: installs python 3.11 + uv, runs `uv sync --frozen --no-dev`. all three services share the same image — only the start command differs.
- required env vars: `DATABASE_URL`, `REDIS_URL`, `OPENROUTER_API_KEY`, `SECRET_KEY`, `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`. optional: `LLM_MODEL` (defaults to a free OpenRouter model — override per environment, e.g. prod = `openai/gpt-4o-mini`), `OPENROUTER_BASE_URL` (defaults to `https://openrouter.ai/api/v1`). all come from railway env / shared variables. railway's postgres + redis addons inject `DATABASE_URL` and `REDIS_URL` automatically when attached.
- tailwind play cdn is fine for early deploys; precompile to `apps/api/static/css/` before going public (separate plan).

## conventions
- all api endpoints async; all celery tasks sync (celery 5 limitation — do not use async def in tasks)
- pydantic v2 schemas for every request/response body and every llm output boundary
- sqlalchemy 2.0 declarative style with Mapped[] type annotations on every column — no legacy style
- routes return raw pydantic models for json endpoints; fastapi handles serialization
- htmx routes return jinja2 TemplateResponse — never return raw html strings
- partial templates (in /templates/partials/) are returned for htmx requests; full page templates for initial page loads
- detect htmx requests via the HX-Request header: `request.headers.get("hx-request")`
- tailwind via cdn in development; compile to static file before any production deploy
- no custom javascript unless htmx cannot achieve the interaction — keep /static/js/ minimal
- ruff for lint + format, mypy strict on /app — both must pass before any commit
- tests live in /apps/api/tests/ mirroring /app structure, named test_*.py
- commits follow conventional commits: feat:, fix:, chore:, refactor:, test:, docs:
- one alembic migration per logical change — never edit a migration that has been applied to any environment
- no comments by default — only add a comment if the code would be genuinely hard to understand without it
- always simplify and modularize over clever or dense solutions

## architecture decisions
- chose fastapi over flask (may 2026): async-native, pydantic-integrated, modern python web standard
- chose sqlalchemy 2.0 over 1.x style (may 2026): typed Mapped[] columns catch model bugs at write-time
- chose celery + redis over fastapi BackgroundTasks (may 2026): cron scheduling via celery beat required for nightly content generation; celery is the production standard for python async work
- chose pydantic v2 over manual validation (may 2026): 5x faster than v1; strict mode + custom validators are the core abstraction for llm output validation
- chose openai sdk targeting openrouter over anthropic sdk (2026-05-04, supersedes earlier may-2026 anthropic call): openrouter is openai-api-compatible so the openai python sdk works as the client; gives access to `:free` models for dev/staging while letting prod swap to any paid model (openai, anthropic, google) by changing the `LLM_MODEL` env var with no code change. dev defaults to `meta-llama/llama-3.3-70b-instruct:free`; prod should pick a paid model with reliable structured-output support. retry-with-prompt-refinement loop already planned absorbs the lower instruction-following quality of free models.
- chose sm-2 over fsrs for spaced repetition (may 2026): simpler to implement and explain, sufficient for poc; fsrs is a candidate upgrade if data volume justifies it
- chose google oauth over password auth (may 2026): simpler for solo/small-user-base, no password storage risk
- chose htmx + jinja2 over next.js (may 2026): spaced-repetition ui is server-driven (show card, reveal, rate, next) — no complex client state; keeps entire stack in python, eliminates context switching, ships faster; next.js is a candidate if a mobile-web hybrid is needed later

## current focus
- daily content generation pipeline: celery beat → selection service → llm enrichment → pydantic validation → persist
- pydantic validators on every llm output: schema shape, semantic constraints (target token must appear in generated example), length bounds, content safety checks
- retry-with-prompt-refinement loop: on validation failure, log violation + tokens spent, refine prompt with failed constraint, retry up to 3 times, fall back to curated default

## rules
- never commit without running ruff and the full test suite first
- never store raw llm output in the database — always validate through a pydantic schema first
- never call an llm without a timeout, retry policy, and structured logging of token cost
- if a task touches more than 3 files or requires a new dependency, write a plan in /plans/ first and show it before writing any code
- new pydantic schemas require at least one happy-path test and one validation-failure test
- migrations are never edited after being applied to any environment — write a new migration instead
- ai-generated code touching auth or user data is rewritten by hand before being accepted
- no comments by default — only where code would be genuinely hard to understand without one
