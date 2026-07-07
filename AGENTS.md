# AGENTS.md

## project
- name: RecallAI
- stack: python 3.11, fastapi (json api only), react 19 spa (vite + tanstack router + tanstack query + zustand, tailwind css v4), postgres via sqlalchemy 2.0 (async), pydantic v2, openai sdk (via openrouter)
- deployed on railway: web service + nightly cron service + postgres addon
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
        /core/                ← config, db engine, logging
        /models/              ← sqlalchemy 2.0 orm models
        /schemas/             ← pydantic v2 schemas (request, response, llm output)
        /services/            ← business logic layer
        /jobs/                ← nightly cron entrypoint + async job functions
      /alembic/               ← migrations (one per logical change)
      /tests/                 ← mirrors /app structure, named test_*.py
      /plans/                 ← pre-coding plan documents (required for 3+ file tasks)
    /web/                     ← react 19 spa (vite + tanstack router + tanstack query + zustand, tailwind css v4)
  /packages/
    /shared/                  ← shared constants, enums, api contract types (if needed)
```

## auth
- google oauth (credentials provided by developer at session start — never hardcode or commit)
- all auth-related code must be written by hand — ai-generated auth logic is not accepted as-is
- user data access must be audited manually before any PR is considered complete

## run / deploy
- `.env` lives at the repo root (copied from `.env.example`); `pydantic-settings` reads it relative to the CWD where uvicorn runs, which is the repo root.
- dev: `pnpm dev` runs the FastAPI json api (uvicorn, `--reload`) and the React SPA (`pnpm --filter web dev`, Vite on :5173) concurrently; Vite proxies `/api`, `/auth` to the api on :8000. open http://localhost:5173 in dev.
- prod (local sanity): `pnpm start` → same command, no `--reload`, binds `0.0.0.0:$PORT` (defaults to 8000).
- nightly content generation runs as a Railway cron service (`railway.cron.json` + `railpack.cron.json`): `cd apps/api && uv run python -m app.jobs.nightly` at 18:00 UTC daily. the entrypoint skips (logs + exits 0) unless `RAILWAY_ENVIRONMENT_NAME=production` or `NIGHTLY_FORCE=1` — so PR-environment clones never burn LLM tokens. run it locally with `NIGHTLY_FORCE=1` (real LLM calls).
- tests: `pnpm test` (full suite) or `uv run pytest <path>` for a single file.
- lint + types: `pnpm lint` runs ruff check + ruff format check + mypy strict on `apps/api/app`.

### ci
- workflow lives at `.github/workflows/ci.yml`. three parallel jobs: `Lint & Test` (ruff + mypy + pytest), `Migration Check` (alembic upgrade/downgrade/upgrade against a postgres:16-alpine service container), `Secret Scan (Gitleaks)`.
- triggers on every push to `main` and every pull request. all jobs must be green before a PR can merge (once branch protection is applied — see `.github/BRANCH_PROTECTION.md`).
- you cannot skip checks. there is no bypass flag, and `enforce_admins: true` applies to repo owners too.
- dependabot config is at `.github/dependabot.yml`. it opens weekly PRs for github-actions, npm, and uv dependencies. minor+patch updates are grouped per ecosystem to reduce noise; major bumps get individual PRs.
- to re-trigger a stuck PR: `gh run rerun <run-id>` or push an empty commit: `git commit --allow-empty -m "chore: retrigger CI" && git push`.

### railway
- one repo, two services. each service has its own railpack config (skips the Node + Tailwind build for the cron service — faster deploys, smaller images) AND its own railway config (so only web runs `alembic upgrade head` pre-deploy). Pair the two config files per service via env vars — no dashboard start-command override needed.
  - **web**: default `railway.json` + `railpack.json`. Railpack installs python + uv + nodejs + pnpm, runs `pnpm install --frozen-lockfile`, `uv sync`, then `pnpm run build` to build the React SPA into `apps/web/dist`. preDeployCommand runs `alembic upgrade head`. Start: uvicorn, which serves the api under `/api` + `/auth` and the built SPA for every other path. `/healthz` healthcheck.
  - **nightly cron**: set `RAILWAY_CONFIG_FILE=railway.cron.json` AND `RAILPACK_CONFIG_FILE=railpack.cron.json`. Railpack installs python + uv only (no Node). No preDeployCommand. `cronSchedule: 0 18 * * *`, `restartPolicyType: NEVER`. Start: `python -m app.jobs.nightly`, which runs shared-pool generation → enrichment → personalized generation sequentially and exits. the entrypoint's env guard (`RAILWAY_ENVIRONMENT_NAME=production` or `NIGHTLY_FORCE=1`) keeps PR-environment clones from burning LLM tokens.
- required env vars (all services): `DATABASE_URL`, `LLM_API_KEY`, `LLM_BASE_URL`, `LLM_MODEL`, `SECRET_KEY`, `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `GOOGLE_REDIRECT_URI`. optional web-only: `SESSION_HTTPS_ONLY` (default `false` for dev; set `true` in prod so the signed session cookie carries the `Secure` flag). **no code-side defaults for the LLM trio nor `GOOGLE_REDIRECT_URI`** — `.env` (dev) and railway env (prod) are the single source of truth, so a missing var fails loudly at startup instead of silently picking a dev model or a localhost callback in prod. swap providers by setting the three `LLM_*` vars together (e.g. dev → OpenRouter + `z-ai/glm-4.5-air:free`; prod → OpenRouter + `deepseek/deepseek-v4-flash` or OpenCode Go's `https://opencode.ai/zen/go/v1` + `deepseek-v4-flash`). railway's postgres addon injects `DATABASE_URL` automatically when attached.
- the SPA build (`apps/web/dist`) is gitignored; `/assets` is mounted from it and served with long-lived caching from Vite's hashed filenames.

## conventions
- all api endpoints async; nightly job functions are async and run under one `asyncio.run` in the cron entrypoint
- pydantic v2 schemas for every request/response body and every llm output boundary
- sqlalchemy 2.0 declarative style with Mapped[] type annotations on every column — no legacy style
- fastapi is json-api only — no server-rendered html; routes return raw pydantic models, fastapi handles serialization
- react spa (apps/web) is the frontend, calling the fastapi json api
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
- chose openai sdk + provider-neutral settings (2026-05-04, refined 2026-05-07; supersedes earlier may-2026 anthropic call): openrouter, opencode go, deepseek-direct, and openai are all OpenAI-API-compatible, so the openai python sdk works against any of them by changing only `LLM_BASE_URL` + `LLM_API_KEY` + `LLM_MODEL` env vars (no code change). all three are required env vars with no code defaults — env files own the per-environment choice. recommended pairings: dev = OpenRouter + `z-ai/glm-4.5-air:free` (smoke-tested 2026-05-07 first-try; the earlier `meta-llama/llama-3.3-70b-instruct:free` returns 402 from upstream). prod options: OpenRouter @ `deepseek/deepseek-v4-flash` (~$0.14 in / $0.28 out per Mtok, pay-per-token, smoke-tested 2026-05-07 first-try @ 66 in + 173 out tokens); or OpenCode Go @ `deepseek-v4-flash` (flat-rate via subscription, smoke-tested 2026-05-07 first-try @ 165 in + 153 out tokens) if call volume fits the user's existing quota. retry-with-prompt-refinement loop absorbs the lower instruction-following quality of free models.
- chose sm-2 over fsrs for spaced repetition (may 2026): simpler to implement and explain, sufficient for poc; fsrs is a candidate upgrade if data volume justifies it
- chose google oauth over password auth (may 2026): simpler for solo/small-user-base, no password storage risk
- migrated from htmx + jinja2 to a react 19 spa: fastapi is now json-api only, apps/web (vite + tanstack router + tanstack query + zustand, tailwind css v4) owns the frontend
- chose railway cron over celery beat + worker (2026-07-07): zero runtime task enqueueing existed — celery only ran 3 nightly beat jobs; one cron service running app.jobs.nightly sequentially replaces 2 always-on services + redis addon, cuts idle cost, makes step ordering explicit; celery is the fallback if runtime enqueueing ever returns

## current focus
- daily content generation pipeline: railway cron (`app.jobs.nightly`) → selection service → llm enrichment → pydantic validation → persist
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

## Agent skills

### Issue tracker

Issues and PRDs live as GitHub issues in `ical10/recall-ai` via the `gh` CLI. See `docs/agents/issue-tracker.md`.

### Triage labels

Five canonical roles, default strings (`needs-triage`, `needs-info`, `ready-for-agent`, `ready-for-human`, `wontfix`). See `docs/agents/triage-labels.md`.

### Domain docs

Single-context: glossary in `GLOSSARY.md`, ADRs inline in this file's architecture-decisions section. See `docs/agents/domain.md`.
