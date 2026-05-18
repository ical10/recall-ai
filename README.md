# RecallAI

Spaced-repetition vocabulary trainer with LLM-generated content for ESL learners.

## Architecture

```
┌──────────┐                                        ┌──────────────┐
│   User   │                                        │ LLM Provider │
│ (browser)│                                        │ (OpenRouter) │
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

**Key relationships:**

- **Web ↔ Postgres**: synchronous reads/writes per HTTP request (user, vocab, reviews). Also runs `alembic upgrade head` during preDeploy.
- **Web ↔ Redis**: web does NOT touch Redis directly. No task enqueueing from the request path.
- **Beat → Redis**: publishes tasks on the cron schedule. Never touches Postgres.
- **Worker ← Redis**: long-poll consumer.
- **Worker → Postgres**: writes generated vocab + bookkeeping (attempts, source, milestones).
- **Worker → LLM provider**: outbound HTTPS for content generation. Beat and Web never call the LLM.
- **Beat is `replicas=1`**: more than one beat = duplicate task enqueueing = duplicate LLM costs. Workers can scale horizontally without that risk.
- **All 3 services share Postgres + Redis**: same Railway project scope, `${{ Postgres.DATABASE_URL }}` and `${{ Redis.REDIS_URL }}` references resolve to the same addons.

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

# 2. Start PostgreSQL + Redis
docker compose up -d

# 3. Install dependencies
pnpm install --frozen-lockfile
uv sync --frozen

# 4. Run migrations and seed sample vocabulary
./scripts/dev_reset.sh
```

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
