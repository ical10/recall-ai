# RecallAI

A spaced-repetition vocabulary trainer with nightly LLM-generated content, built for English-as-a-Second-Language learners.

> Five minutes a day. The words stick — because you caught them right before you forgot.

RecallAI takes the forgetting curve seriously. Instead of shipping a static deck and hoping users grind through it, the app **generates a fresh, personalised batch of vocabulary every night** (kid-safe sentences, age-appropriate definitions, topics that match the learner's interests) and schedules every word using the classic **SM-2** algorithm — the same engine Anki has shipped for two decades. Easy words drift weeks into the future; hard words come back tomorrow.

---

## Why this exists

Two things have to be true for vocabulary to actually stick:

1. **The content has to be worth learning** — relevant, age-appropriate, and tied to topics the learner cares about.
2. **The review timing has to match the forgetting curve** — words seen too often waste attention; words seen too rarely fade.

Generic deck apps nail the timing but leave curation to the learner. Most kids (and most parents) don't curate. RecallAI takes both jobs off the table: **an LLM generates a personalised batch of cards every night, and SM-2 decides exactly when each card resurfaces.** The learner just shows up.

---

## Architecture

```
┌──────────┐                                        ┌──────────────┐
│   User   │                                        │ LLM Provider │
│ (browser)│                                        │  (external)  │
└────┬─────┘                                        └──────▲───────┘
     │ HTTPS                                               │
     │ OAuth + review UI                                   │ POST /chat
     ▼                                                     │ completions
┌─────────────────┐   ┌──────────────────┐   ┌─────────────┴──────┐
│   Web service   │   │   Beat service   │   │   Worker service   │
│  (recall-ai)    │   │     replicas=1   │   │                    │
│  FastAPI+uvicorn│   │  Celery scheduler│   │   Celery worker    │
│  Tailwind+htmx  │   │ 18:00 + 19:00 UTC│   │  consumes tasks    │
└────┬────────────┘   └────────┬─────────┘   └─────┬─────────▲────┘
     │                         │ enqueues          │ persists│ pulls
     │ session +               │ scheduled tasks   │ vocab + │ tasks
     │ user CRUD               ▼                   │ reviews │
     │           ┌───────────────────────────┐     │         │
     │           │       Redis (addon)       │◄────┘         │
     │           │   broker + result backend │───────────────┘
     │           └───────────────────────────┘
     │                         ▲
     │ alembic migrations      │ (worker does NOT pub here;
     │ (preDeployCommand)      │  it only consumes)
     ▼                         │
┌─────────────────────────────────────────────────┐
│              Postgres (addon)                   │
│  users · vocab_items · reviews · interest_tags  │
└─────────────────────────────────────────────────┘
                       ▲
                       │ persists vocab generation results
                       └─── (from Worker)
```

### How the three services collaborate

| Service    | Process              | Responsibility                                          | Talks to                 |
| ---------- | -------------------- | ------------------------------------------------------- | ------------------------ |
| **web**    | `uvicorn` (async)    | OAuth, review UI, dashboard, settings, HTMX partials    | Postgres                 |
| **beat**   | Celery beat (cron)   | Enqueues nightly content-generation tasks (UTC 18 & 19) | Redis                    |
| **worker** | Celery worker (sync) | Pulls tasks, calls LLM, validates, persists vocab       | Redis, Postgres, LLM API |

Key design choices baked into the topology:

- **Web never calls the LLM.** Request-path latency stays bounded; LLM hiccups can't 500 the dashboard.
- **Beat has `replicas=1`** in production. Duplicate beats = duplicate enqueues = duplicate API spend.
- **Worker is the only writer of generated content.** All LLM output flows through a Pydantic v2 validator before it touches Postgres.
- **Alembic runs as a Railway `preDeployCommand` on the web service only.** Worker and beat reuse the migrated schema; they never race the migrator.

---

## The learning loop

```
   18:00 UTC                                           Next morning
       │                                                    │
       ▼                                                    ▼
┌──────────────┐    enqueue     ┌──────────┐  pull  ┌────────────┐
│  Celery beat │───────────────►│  Redis   │───────►│   Worker   │
└──────────────┘                └──────────┘        └─────┬──────┘
                                                          │
                                       LLM call (timeout, ▼ retry, log tokens)
                                          ┌────────────────────────┐
                                          │      LLM Provider      │
                                          └─────────┬──────────────┘
                                                    │ raw JSON
                                                    ▼
                                          ┌────────────────────────┐
                                          │  Pydantic v2 validator │
                                          │  (shape + semantic +   │
                                          │   length + safety)     │
                                          └─────────┬──────────────┘
                                                    │ pass / refine / fallback
                                                    ▼
                                          ┌────────────────────────┐
                                          │ Postgres: vocab_items  │
                                          │            + reviews   │
                                          └─────────┬──────────────┘
                                                    │
                          User opens /review        ▼
                                          ┌────────────────────────┐
                                          │   Show card → rate     │
                                          │   SM-2 picks next date │
                                          └────────────────────────┘
```

Every LLM call is wrapped in:

- A **hard timeout** (no retries-from-hell on a hanging upstream).
- A **structured cost log** (tokens in, tokens out, model, latency).
- A **retry-with-prompt-refinement loop**: on validation failure, refine the prompt with the failed constraint and retry up to 3 times before falling back to a curated default.
- **Idempotency markers** so a retried Celery task can't double-enqueue spend.

---

## Tech stack

| Layer         | Choice                                             | Rationale                                                   |
| ------------- | -------------------------------------------------- | ----------------------------------------------------------- |
| Language      | Python 3.11                                        | Mature async, modern typing                                 |
| Web framework | FastAPI                                            | Async-native, Pydantic-integrated                           |
| Frontend      | Jinja2 + HTMX + Tailwind                           | Server-rendered, no SPA complexity for a server-driven UI   |
| ORM           | SQLAlchemy 2.0 (async) with typed `Mapped[]`       | Write-time typing catches model bugs                        |
| Validation    | Pydantic v2 (strict)                               | The LLM-output safety boundary                              |
| Database      | Postgres 16                                        | Standard; Railway addon in prod, Docker in dev              |
| Queue / cache | Redis 7                                            | Celery broker + result backend                              |
| Async work    | Celery 5 (worker + beat)                           | Cron scheduling for nightly content                         |
| LLM access    | OpenAI Python SDK against an OpenAI-compatible API | Swap providers via three env vars; no code change required  |
| Auth          | Google OAuth                                       | No password storage, no liability                           |
| Spacing       | SM-2                                               | Simple, well-understood, sufficient for the data scale      |
| Migrations    | Alembic                                            | One migration per logical change, never edited post-deploy  |
| Lint / types  | Ruff + mypy strict                                 | Both must pass before commit                                |
| Tests         | pytest                                             | Happy-path + validation-failure per Pydantic schema         |
| Monorepo      | pnpm workspaces + Turborepo                        | One repo, three Railway services                            |
| Hosting       | Railway (web + worker + beat + Postgres + Redis)   | One project, per-service `railway.*.json` configs           |

---

## Prerequisites

- [Docker](https://docs.docker.com/get-docker/)
- [uv](https://docs.astral.sh/uv/)
- [pnpm](https://pnpm.io/installation) (v9+)

## Setup

```bash
# 1. Copy and fill in your credentials
cp .env.example .env
# Edit .env — fill LLM_API_KEY, LLM_BASE_URL, LLM_MODEL,
#   GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET, SECRET_KEY.

# 2. Install dependencies
pnpm install --frozen-lockfile
uv sync --frozen

# 3. Run migrations and seed sample vocabulary
./scripts/dev_reset.sh
```

(Postgres and Redis start automatically — `pnpm dev`, `pnpm worker`, and `pnpm beat` all run `docker compose up -d` before their main process.)

## Running

```bash
pnpm dev      # web server → http://127.0.0.1:8000
pnpm worker   # Celery worker (LLM content generation)
pnpm beat     # Celery beat (daily scheduling)
```

## Run the full stack in Docker

End-to-end smoke test of the deploy artifact (Postgres + Redis + the web image Railway will run):

```bash
cp .env.example .env   # set GOOGLE_CLIENT_*, LLM_*, SECRET_KEY
docker compose up --build
```

`pnpm dev` is still the recommended dev loop — it gives you Tailwind + uvicorn hot reload. The Docker target is for verifying the production-shaped image locally.

## Reset database

Wipe everything and re-seed from scratch:

```bash
docker compose exec postgres psql -U user -d postgres \
  -c "DROP DATABASE recallai;"
docker compose exec postgres psql -U user -d postgres \
  -c "CREATE DATABASE recallai;"
./scripts/dev_reset.sh
```

## Teardown

```bash
docker compose down      # stop, keep data
docker compose down -v   # stop, wipe data
```

---

## Project layout

```
apps/api/
  app/
    api/         route handlers (async)
    core/        config, db engine, celery app, logging
    models/      SQLAlchemy 2.0 ORM (users, vocab_items, reviews)
    schemas/     Pydantic v2 (request, response, LLM-output contracts)
    services/    business logic (sm2, selection, enrichment, llm, stats)
    workers/     Celery tasks (sync only — Celery 5 constraint)
  templates/     Jinja2 (pages/ + partials/)
  static/        Tailwind output + minimal JS
  alembic/       migrations
  tests/         mirrors app/ structure
packages/shared/ shared enums + constants
.github/         CI (ruff + mypy + pytest + alembic round-trip + gitleaks)
railway.*.json   per-service deploy config (web / worker / beat)
railpack.*.json  per-service build config
```

---

## Roadmap

Things on the radar, not promises:

- **FSRS upgrade.** SM-2 is great for a POC, but FSRS adapts per-card difficulty better once there's enough review data to justify it.
- **Audio cards.** TTS for pronunciation; STT for spoken-answer rating. The recall side, not the recognition side.
- **Image associations.** Auto-pair generated examples with safe stock imagery — visual memory anchor for ages 5–12.
- **PWA / offline review.** Cache the next 50 due cards client-side so a kid can review on a tablet without a connection.
- **Parent dashboard.** Weekly progress summary email, retention curves, words mastered.
- **Multi-language support.** Today: English. Same SM-2 + LLM pipeline applies to any vocabulary target.
- **Cost dashboard.** Per-user, per-day LLM spend with hard caps; alerts if a single user blows past a threshold.
- **A/B-able prompt registry.** Version prompts in the DB instead of code so quality regressions can be diffed.

---

## Assumptions and limitations

Worth being upfront about:

- **Target audience is narrow.** Designed for ESL learners aged ~5–12 (the Novakid demographic). Generated content, tags, and prompts are explicitly kid-safe and age-tuned. It is not a TOEFL prep app.
- **English-only at the moment.** The pipeline isn't language-locked, but the prompt library and content-safety checks are.
- **The operator pays the LLM bill.** Every nightly batch is a real API call against whichever provider `LLM_BASE_URL` points at; whoever deploys the app eats that cost. The retry-with-refinement loop, capped `max_tokens`, and idempotency markers keep spend bounded, but a misconfigured prompt can still burn tokens before the cap kicks in.
- **Provider compatibility is broad in theory, narrow in practice.** Any OpenAI-API-compatible endpoint should work, swapped via the three `LLM_*` env vars. In practice only **OpenRouter** (free + paid tiers) and **OpenCode Go** have been smoke-tested end-to-end. Other compatible providers (Groq, Together AI, direct OpenAI, self-hosted vLLM) should work but haven't been verified.
- **SM-2, not FSRS.** Chosen for simplicity and explainability. Optimal review timing is sacrificed for predictability — fine for the data scale, not optimal for it.
- **HTMX over SPA.** Means most interactions are full-page round trips (cheap, but visible on slow links). Acceptable for the review-card flow; would not scale to a complex multi-pane UI.

---

## Disclaimer

RecallAI is a **personal project**. It is not affiliated with, endorsed by, or sponsored by any third-party platform, LLM provider, or tool referenced in this document.

LLM-generated content can contain factual errors, awkward phrasing, or culturally insensitive outputs even with validation in place. The retry-with-refinement loop reduces this risk; it does not eliminate it. Treat all generated material as draft-quality educational content, not authoritative reference material. If you deploy this for real learners, **review the generated corpus periodically** and keep a kill-switch on the nightly job.

The codebase is provided as-is; see [LICENSE](./LICENSE).

---

## License

MIT — see [LICENSE](./LICENSE).
