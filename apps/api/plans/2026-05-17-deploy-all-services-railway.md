# Deploy All Services to Railway — PRD

**Author:** ops
**Date:** 2026-05-17
**Status:** Ready to execute

## Why

The repo has three deployable services — FastAPI web, Celery worker, Celery beat — plus Postgres + Redis addons. The web service is already running on Railway. Worker + beat have nixpacks configs ready (per [2026-05-07-railway-worker-beat-deploy.md](2026-05-07-railway-worker-beat-deploy.md)) but were never activated, and a deployment-readiness audit (2026-05-17) found three code-side gaps that block a clean production cut:

1. **Migrations don't run on deploy.** No release phase, no startup hook. Schema drift is a manual fix.
2. **`GOOGLE_REDIRECT_URI` has a localhost default in code** (`config.py:18`). Prod sign-in breaks silently if the env var isn't set on the Railway side.
3. **Session cookie has `https_only=False`** (`main.py:34`). The signed session cookie travels over HTTP in dev *and* prod with the current code.

This PRD covers code fixes + the Railway-side rollout to get worker + beat live alongside web, all in one Railway project, sharing the same Postgres + Redis addons.

## Scope

In:
- Run Alembic migrations automatically on web service deploy.
- Make `GOOGLE_REDIRECT_URI` a required env var (no code default).
- Make `https_only` env-driven (default true in prod, false in dev).
- Add `GOOGLE_*` env vars to the worker + beat env contract documentation (worker hits the DB via SQLAlchemy → models import from same package → don't need OAuth vars at runtime, but should fail loud at startup if `Settings` validation expects them).
- Activate worker + beat services in the existing Railway project, attached to the existing Postgres + Redis addons.
- Smoke-verify: `/healthz` returns ok; worker logs show the Celery banner + registered tasks; beat logs show `Starting...` and fires at least one scheduled task at the next tick.

Out:
- Sentry / OpenTelemetry / structured JSON logging — deferred until error volume justifies.
- An explicit GitHub Actions deploy workflow — Railway's auto-deploy on `main` is sufficient.
- Switching beat to RedBeat/DatabaseScheduler — ephemeral disk is fine for the current cadence.
- Custom domain + DNS — Railway-provided subdomain works for now.

## Gaps & Decisions

### Gap 1 — Migrations on deploy
**Decision:** Add a `releaseCommand` to `railway.json` that runs `alembic upgrade head` against `DATABASE_URL` before swapping in the new web container.
**Why over startup hook:** A release phase fails the deploy if the migration breaks, blocking a bad release. A startup hook would crash-loop every replica.
**Worker + beat:** They share the same DB but should not run migrations (race risk). Migrations stay web-only.

### Gap 2 — `GOOGLE_REDIRECT_URI` localhost default
**Decision:** Remove the default. Make it required like the other prod-critical vars (`SECRET_KEY`, `LLM_*`).
**Migration:** Update `.env.example` to make the local value explicit. Existing dev `.env` files already set it.

### Gap 3 — `https_only` hardcoded false
**Decision:** Add `session_https_only: bool = False` to `Settings`. Default false (dev-safe); Railway sets `SESSION_HTTPS_ONLY=true` per service.
**Why an env var, not auto-detect:** Explicit > magical. The CLAUDE.md rule "no raw external input without validation" extends to environmental assumptions — better to require the operator to opt in than to infer from `RAILWAY_ENVIRONMENT` or similar.

### Env contract — final shape

| Var | Web | Worker | Beat | Notes |
|---|---|---|---|---|
| `DATABASE_URL` | ✓ | ✓ | ✓ | Injected by Railway Postgres addon reference |
| `REDIS_URL` | ✓ | ✓ | ✓ | Injected by Railway Redis addon reference |
| `LLM_API_KEY` | ✓ | ✓ | ✓ | Worker needs for content_gen tasks; web needs for inline LLM calls if any |
| `LLM_BASE_URL` | ✓ | ✓ | ✓ | Same reason |
| `LLM_MODEL` | ✓ | ✓ | ✓ | Same reason |
| `SECRET_KEY` | ✓ | ✓ | ✓ | Settings requires it; cleaner to set everywhere than make worker/beat use a separate Settings subset |
| `GOOGLE_CLIENT_ID` | ✓ | ✓ | ✓ | Same reason — Settings requires presence in code |
| `GOOGLE_CLIENT_SECRET` | ✓ | ✓ | ✓ | Same |
| `GOOGLE_REDIRECT_URI` | ✓ | ✓ | ✓ | Same; worker/beat value can stay localhost-ish, only web uses it |
| `SESSION_HTTPS_ONLY` | `true` (prod) | — | — | New; web only |
| `NIXPACKS_CONFIG_FILE` | — | `nixpacks.worker.toml` | `nixpacks.beat.toml` | Service-specific |
| `CONTENT_DENYLIST` | optional | optional | optional | Already optional |

**Variables NOT to set in Railway:** `PORT` (Railway injects), `RAILWAY_*` (Railway injects), `NODE_VERSION` / `PYTHON_VERSION` (nixpacks pins).

**Variables to remove from `.env.example`:** none — all current entries match the new contract.

### Railway project scope

User confirmed they have a Railway account and wants all services in the same project. The existing project already hosts the web service + Postgres + Redis. Worker + beat will be added as additional services in the **same project**, referencing the existing addons via `${{ Postgres.DATABASE_URL }}` and `${{ Redis.REDIS_URL }}` — no second DB / Redis needed.

**Access I need from the user:** if any Railway-side action fails (auth, billing, missing project link), the user runs the Railway CLI command locally. I'll provide each command verbatim and label it "user runs."

## Success Criteria

- [ ] `alembic upgrade head` runs as part of the web service release; a deploy with a bad migration fails the release rather than the container.
- [ ] Local `pnpm dev` still works with the existing `.env` (no change in dev UX).
- [ ] Web service deploys clean; `/healthz` returns 200.
- [ ] `curl -I https://<web-domain>/healthz` shows no `Set-Cookie` over HTTP (cookie only set on HTTPS).
- [ ] Worker service deploys with no Node + no pnpm in the build log; logs show Celery banner + 2 registered tasks (`content_gen.run_daily`, `content_gen.generate_shared_pool`).
- [ ] Beat service deploys with `replicas=1`; logs show `[INFO/Beat] beat: Starting...`.
- [ ] `celery inspect ping` against prod Redis returns `pong` from the worker.
- [ ] At the next 18:00 / 19:00 UTC tick, beat queues the task → worker picks it up → log line confirms run.

## Plan / Tracer-Bullet Slices

Each slice ships independently; ordering reflects deploy dependencies.

### Slice 1 — Code: migration release phase
- Add `releaseCommand` to `railway.json`: `uv run alembic -c apps/api/alembic.ini upgrade head`
- Verify the command runs locally against a clean DB.
- Verify the Alembic config picks up `DATABASE_URL` from env (it does today via `apps/api/alembic/env.py`).

### Slice 2 — Code: required `GOOGLE_REDIRECT_URI`
- Remove the default from `Settings.google_redirect_uri` in `apps/api/app/core/config.py`.
- Update `.env.example` (no functional change; comment that it's required).
- Confirm test fixtures set the var (audit any `Settings()` calls in tests).

### Slice 3 — Code: env-driven `https_only`
- Add `session_https_only: bool = False` to `Settings`.
- Wire it into `SessionMiddleware(https_only=...)` in `apps/api/app/main.py:34`.
- Document in `.env.example` and CLAUDE.md run/deploy section.

### Slice 4 — Railway: worker service activation
- User creates the worker service in the existing project (per the 2026-05-07 checklist).
- Set the env contract from the table above.
- Confirm build skips Node phase; confirm Celery banner.

### Slice 5 — Railway: beat service activation
- Repeat for beat. `replicas=1` is non-negotiable (duplicate tasks otherwise).
- Wait at most 1 hour for the 18:00 or 19:00 UTC tick to verify the loop end-to-end. If outside that window, manually invoke a task via the worker shell to short-circuit verification.

### Slice 6 — Railway: web service env updates
- Add `SESSION_HTTPS_ONLY=true` to the existing web service.
- Confirm `GOOGLE_REDIRECT_URI` is already set on the prod web domain (it must be — OAuth would have been broken otherwise). If not, set it.
- Trigger a redeploy; confirm `/healthz` and OAuth sign-in still work.

## Rollback

Per slice:
- **Slice 1:** Remove `releaseCommand` from `railway.json`. Next deploy reverts to no release phase.
- **Slice 2:** Re-add the default in `config.py`. Push.
- **Slice 3:** Set `SESSION_HTTPS_ONLY=false` in Railway. No code change needed.
- **Slice 4/5:** Delete the worker/beat service in Railway. Schedule stops firing; web unaffected.
- **Slice 6:** Unset `SESSION_HTTPS_ONLY` (defaults to false). Redeploy.

## Open Questions

None — gaps and decisions are concrete. If a Railway-side step fails, surface the exact error and pause.
