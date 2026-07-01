# Plan — Tier 3: replace always-on worker + beat with a Railway cron (run-and-exit)

## Context
`recall-ai-worker` ($4.47) + `recall-ai-beat` ($1.61) are **~75% of Railway spend** ($6.08 of $8.14),
running **24/7** purely to serve **3 nightly tasks** (18/19/20:00 UTC in `celery_app.py`). Exploration
confirms the workload fits a run-and-exit cron with no compromise:
- **No runtime task enqueueing** — nothing calls `.delay()`/`.apply_async()`; tasks fire *only* via beat.
- **Redis serves only Celery** — it is the broker/backend and nothing else (`config.py:redis_url` is used
  only in `celery_app.py`).
- **`render_audio`/`backfill_audio` are not scheduled or enqueued anywhere** — the nightly flow is just
  the 3 content-gen functions.

**Goal:** run the nightly pipeline as a single Railway **cron service** that spins up, runs the batch in
order, and exits — billed only for the minutes it runs — and **decommission worker, beat, and Redis**.

**ADR impact:** reopens the "celery + redis over BackgroundTasks (cron via beat)" decision and touches
ADR-0003 (tasks use `asyncio.run`). Justified: the workload is tiny, nightly, single-user, with zero
runtime enqueueing — the always-on broker/worker model earns nothing here. **ADR-0003's `asyncio.run`
pattern is preserved** (the cron entrypoint still `asyncio.run`s the same async impls).

---

## Recommended approach — Option B: keep the task code, schedule via cron (low churn)
Calling a Celery task **directly** (`run_daily()`) runs its body **synchronously in-process, without a
broker**. So we keep `app/workers/content_gen.py` unchanged and add a thin cron entrypoint that calls the
three tasks in order. This gets the **full cost win** (no worker, no beat, no Redis always-on) with
minimal code change and keeps the task abstraction + existing tests intact.

*(Alternative — Option A: fully strip Celery + Redis, converting tasks to plain async functions. More
churn for marginal further benefit; do later as cleanup if we want to shed the dependency.)*

### New files
- **`apps/api/app/workers/nightly.py`** — the cron entrypoint. Runs the pipeline in deterministic order
  (shared pool → enrichment → personalized), replacing the time-spaced beat ticks:
  ```python
  import logging
  from app.workers.content_gen import (
      generate_personalized_for_all, generate_shared_pool, run_daily,
  )
  logger = logging.getLogger(__name__)

  def main() -> None:
      logger.info("nightly_start")
      logger.info("nightly_shared_pool", extra={"result": generate_shared_pool(count=10)})
      logger.info("nightly_run_daily", extra={"result": run_daily(batch_size=25)})
      logger.info("nightly_personalized", extra={"result": generate_personalized_for_all(count=5)})
      logger.info("nightly_done")

  if __name__ == "__main__":
      logging.basicConfig(level=logging.INFO)
      main()
  ```
  Ordering is now explicit (shared pool creates words → personalized excludes them) instead of relying on
  1-hour beat gaps — strictly better. Each task keeps its **idempotency guard** (shared-pool same-day
  skip, run_daily enriches only unenriched, personalized milestone guard), so a re-run is safe.
- **`railway.cron.json`** (mirror `railway.worker.json`, python-only build):
  ```json
  {
    "$schema": "https://railway.app/railway.schema.json",
    "build": { "builder": "RAILPACK" },
    "deploy": {
      "startCommand": "sh -c 'cd apps/api && uv run --project ../.. python -m app.workers.nightly'",
      "cronSchedule": "0 18 * * *",
      "restartPolicyType": "NEVER"
    }
  }
  ```
  - `cronSchedule` `0 18 * * *` = 18:00 UTC daily (verify Railway honours `cronSchedule` in config-as-code;
    if not, set it in the service's Deploy → Cron Schedule UI).
  - `restartPolicyType: NEVER` — a failed run must NOT crash-loop (would re-spend LLM); it retries next
    night. Idempotency guards make the next run safe.
- **`railpack.cron.json`** (mirror `railpack.worker.json`, python-only — skips Node/Tailwind):
  ```json
  { "$schema": "https://schema.railpack.com", "provider": "python",
    "packages": { "python": "3.11" },
    "deploy": { "startCommand": "sh -c 'cd apps/api && uv run python -m app.workers.nightly'" } }
  ```

### Edited files
- **`apps/api/app/core/celery_app.py`** — remove `beat_schedule` (no beat). Change broker/backend off
  Redis so the app constructs without it: `broker="memory://"`, `backend="cache+memory://"` (direct task
  calls never touch the broker; `memory://` just satisfies the constructor). Keep `imports=(...)`.
- **`apps/api/app/core/config.py`** — remove `redis_url` (no longer used).
- **`.env.example`** — drop `REDIS_URL`.
- **`package.json`** — replace `worker`/`beat` scripts with `"nightly": "cd apps/api && uv run python -m
  app.workers.nightly"`; drop `docker compose up` for Redis from dev scripts (Postgres only). Keep the
  compose file's Postgres service.
- **`CLAUDE.md`** — rewrite the `### railway` deploy section: three services → **web + cron** (no worker,
  no beat, no Redis addon); update env-vars list (drop `REDIS_URL`); note the cron config-file pairing.

### Deleted (after the cron is verified live — see rollout)
- `railway.worker.json`, `railpack.worker.json`, `railway.beat.json`, `railpack.beat.json`.

### Tests
- **`apps/api/tests/workers/test_nightly.py`** (new) — mock the three `content_gen` tasks; assert `main()`
  calls them **once each, in order** (shared_pool → run_daily → personalized).
- Existing `test_content_gen.py` is unchanged (it tests the `_run_daily` etc. impls, which don't move).
- If any test asserts the beat schedule / `redis_url` config, update or remove it. `conftest`'s
  `REDIS_URL` setdefault becomes a harmless no-op.

---

## Rollout (staged — no gap in nightly runs)
1. **Merge the code** (cron entrypoint + `railway.cron.json`/`railpack.cron.json` + celery/config edits).
   Keep the worker/beat *services* running for now — deleting their config files doesn't stop the live
   services until you remove them in the dashboard.
2. **Create the cron service** in Railway from `railway.cron.json` (set `RAILWAY_CONFIG_FILE=railway.cron.json`
   + `RAILPACK_CONFIG_FILE=railpack.cron.json`). Env it needs: `DATABASE_URL`, `LLM_API_KEY`, `LLM_BASE_URL`,
   `LLM_MODEL` (content-gen only — **not** the auth/R2/voice vars, since the nightly path doesn't touch them).
3. **Verify one live run** — trigger the cron manually (Railway "Run now" / redeploy) and confirm logs show
   `nightly_shared_pool/run_daily/personalized` with sane counts and no errors; check the DB got new/enriched rows.
4. **Decommission**: delete the `recall-ai-beat` and `recall-ai-worker` services, then remove the **Redis addon**.
5. **Commit the config-file deletions** + the `CLAUDE.md`/`.env.example` updates.

## Verification
- Local: `pnpm nightly` (or `cd apps/api && uv run python -m app.workers.nightly`) runs the pipeline
  end-to-end against a dev DB; `pnpm lint` + `pnpm test` green (incl. `test_nightly`).
- Prod: the scheduled cron fires at 18:00 UTC, completes in one short run, exits; the next morning the deck
  has fresh shared-pool + personalized words and enriched definitions — same outcome as beat, at a fraction
  of the RAM-minutes.
- Cost: `recall-ai-worker` + `recall-ai-beat` disappear from "Cost by Service"; a small `recall-ai-cron`
  line appears billed only for its nightly minutes. Redis line gone.

## Risks & rollback
- **Cron not firing / config-as-code gap:** if `cronSchedule` isn't picked up from JSON, set it in the UI.
  Rollback = re-enable beat + worker services (their config files still in git history) until sorted.
- **Long run overshoot:** the nightly LLM batch must finish within a reasonable window; `run_daily`/generate
  are network-bound (LLM calls) but small (25 / 10 / 5). If it ever grows, split into multiple cron jobs.
- **Idempotency on re-run:** guarded (same-day/milestone/unenriched checks) — a manual re-run won't double
  content or double-spend materially.
- **Kept escape hatch:** Option A (drop Celery/Redis entirely) remains available later; this plan leaves the
  task code and abstraction intact.

## ADR update (do as part of this)
Record a new ADR (or amend the celery decision in `CLAUDE.md` + ADR-0003): "Nightly content generation runs
as a Railway cron (run-and-exit) calling the task functions in-process, not an always-on Celery worker+beat
+ Redis — chosen for cost on a tiny nightly single-user workload with no runtime enqueueing. `asyncio.run`
task pattern (ADR-0003) preserved. Revisit if runtime/async fan-out or high task volume returns."

## Expected impact
Removes the two largest cost lines (worker+beat, ~75%) and the Redis line, replacing them with a cron billed
for a few minutes/day. Combined with the merged Tier 1/2, total should fall from ~$8 toward the
web+Postgres floor (~$2–3).
