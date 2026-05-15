# RecallAI

Spaced-repetition vocabulary trainer with LLM-generated content for ESL learners.

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
