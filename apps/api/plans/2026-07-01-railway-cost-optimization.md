# Plan — Railway cost optimization (worker RAM)

## Context
Railway "Cost by Service" (2026-07-01, minutely-accumulated values):

| Service | RAM (GB-min) | Cost | Share |
|---|---|---|---|
| **recall-ai-worker** | **19,314.94** | **$4.47** | **55%** |
| recall-ai-beat | 6,958.46 | $1.61 | 20% |
| recall-ai-web | 6,607.28 | $1.55 | 19% |
| Postgres | 1,287 | $0.33 | 4% |
| Redis | 430 | $0.19 | 2% |
| **Total** | | **$8.14** | |

**Read the meter:** cost is ~99% **RAM** (CPU/egress/volume are ~$0). The **worker is the outlier** —
~3× the web service's RAM, which is inverted: a background worker on a nightly, single-user workload
should be the *leanest* service, not the heaviest. Absolute spend is small, but the worker is clearly
mis-sized, and the fix is nearly free.

## Root cause (confirmed from config, not guessed)
- **`--concurrency=4`** in `railway.worker.json` **and** `railpack.worker.json` → Celery prefork runs
  **1 parent + 4 child processes**, each importing the full app stack (SQLAlchemy, openai, boto3,
  google-genai, redis). Prefork children share pages copy-on-write, so it's ~3× (not 5×) web — which
  is exactly the ratio observed.
- **No `worker_max_tasks_per_child`** (`celery_app.py`) → child processes never recycle, so peak memory
  from any task is held for the life of the process (fragmentation / leak amplifier).
- **No `worker_max_memory_per_child`** and **no service RAM limit** → nothing caps growth.
- **Eager heavy import:** `import boto3` at module top of `app/services/tts.py` loads boto3 into *every*
  worker child (and beat, via `imports=("app.workers.content_gen",)`) even though audio tasks rarely run.
- **Always-on for nightly bursts:** the only scheduled work is 3 beat tasks (18/19/20:00 UTC,
  `celery_app.py`). The worker is idle ~23.9 h/day still holding all 5 processes' RAM. **The cost is the
  idle baseline × process count, not task spikes** — so concurrency is the lever, not task tuning.

## Phase 1 — Identify / measure (before cutting)
1. Railway → **worker service → Metrics**: read steady-state vs peak RSS **per replica**, and confirm
   the **replica count** (multiplies everything; expected 1).
2. Confirm the live start command uses `--concurrency=4` (both config files do).
3. Add lightweight RSS logging around task start/end (or let `worker_max_memory_per_child` surface it)
   to distinguish **idle baseline** from **per-task growth** (leak vs flat).
4. Check Redis queue depth + nightly task durations so we don't under-provision (a night's batch is
   `batch_size=25` + `count=10` + `count=5` — trivially sequential).
5. Compare beat RSS — it loads the task modules (`imports=...`) it doesn't need for scheduling.

## Phase 2 — Fixes (ordered: cheapest/safest → structural)

### Tier 1 — config-only, high leverage, low risk (do first, one at a time)
- **Drop worker concurrency: `--concurrency=1`** (or 2) in **`railway.worker.json`** +
  **`railpack.worker.json`**. Solo/nightly work runs fine sequentially. Removes 3 children's private
  pages — the single biggest win.
- **`worker_max_tasks_per_child = 100`** (`celery_app.conf`) — recycle children to release accumulated RAM.
- **`worker_max_memory_per_child = 300000`** (KB ≈ 300 MB) — hard cap; auto-restart a bloated child.
- **`worker_prefetch_multiplier = 1`** — hold less reserved work.
- Set a **RAM limit** on the worker service in Railway (e.g. 512 MB) so it can't balloon; if it
  OOM-restarts, bump deliberately.

### Tier 2 — code (ops-adjacent, tiny)
- **Lazy-import boto3** in `app/services/tts.py` (move `import boto3` into `_upload_to_r2`), matching the
  already-lazy `google-genai`. Trims base RSS in every worker/beat process.

### Tier 3 — structural (biggest saving, bigger change; reopens an ADR)
- The worker **and** beat run 24/7 to serve **3 nightly tasks** — together **$6.08 (75%)** of spend.
  Replace the always-on worker + beat with **Railway scheduled/cron services** that spin up, run the
  batch, and exit → pay for minutes run, not 24 h. **This contradicts the celery+redis ADR** (celery
  beat was chosen for cron scheduling) — worth reopening *because* the workload is tiny and nightly and
  cost is the real friction. If we stay on celery, Tier 1 is the mitigation.

## Phase 3 — Verify
- Apply Tier 1 changes **one at a time**; redeploy; watch the worker RAM metric for 24–48 h.
- Confirm nightly `content_gen.run_daily` / `generate_shared_pool` / `generate_personalized_for_all`
  still complete, no Redis backlog, unchanged succeeded/failed counts.
- Roll back the specific change if throughput regresses.

## Expected impact
- **Tier 1 alone:** worker RAM roughly toward web's level → worker cost ~$1.5–2 (from $4.47); total
  ~$5–6 (≈30–40% cut). Realistic, not a 4× cut, because prefork children share pages (CoW).
- **+ Tier 3:** removes most of the worker+beat idle cost → total could approach the Postgres/Redis/web
  floor (~$2–3).

## Guardrails / notes
- Ops change: Tier 1 is config-only; the boto3 lazy-import is the only app-code touch (small).
- **Keep beat `replicas = 1`** (already) — duplicate beat = duplicate task enqueue = duplicate LLM cost.
- Measure before dropping concurrency below a night's batch need.
- Touches `railway.worker.json`, `railpack.worker.json`, `celery_app.py`, `tts.py` → planned (this doc)
  per the 3+-file rule.
