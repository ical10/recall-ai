# Railway Worker + Beat Deploy Checklist

Per-service nixpacks files (`nixpacks.worker.toml`, `nixpacks.beat.toml`) skip the Node + Tailwind build for non-web services. This is the deploy procedure for activating them.

## Pre-flight
- [ ] Branch pushed to remote (or merged to deploy branch)
- [ ] Web service latest deploy is green
- [ ] Postgres + Redis addons attached to project

## Worker service
- [ ] Project → "+ New" → GitHub Repo → same repo + branch. Rename service to `worker`.
- [ ] Variables:
  - `NIXPACKS_CONFIG_FILE=nixpacks.worker.toml`
  - `DATABASE_URL=${{ Postgres.DATABASE_URL }}`
  - `REDIS_URL=${{ Redis.REDIS_URL }}`
  - `OPENROUTER_API_KEY`, `SECRET_KEY` (and `LLM_MODEL` if overriding)
- [ ] Settings → clear Healthcheck Path AND Custom Start Command (both must be empty so the nixpacks file wins)
- [ ] Deploy. Build log shows: no `nodejs_22`, no `pnpm install`, no build phase. Start runs `... celery ... worker`.
- [ ] Logs show Celery banner + registered tasks

## Beat service
- [ ] Repeat above with name `beat`, `NIXPACKS_CONFIG_FILE=nixpacks.beat.toml`, replicas = **1**
- [ ] Logs show `[INFO/Beat] beat: Starting...`

## Verify
- [ ] From local, with prod `REDIS_URL` injected via Railway CLI (`railway link`, then `railway run -s worker -- uv run --project . celery -A app.core.celery_app:celery_app --workdir apps/api inspect ping`) or sourced from a gitignored `.env.prod` — never paste the URL inline (leaks to shell history). Expect `pong`.
- [ ] Worker/beat build durations noticeably shorter than web

## If it breaks
- Build still pulls Node → `NIXPACKS_CONFIG_FILE` not honored. Try `NIXPACKS_CONFIG` instead, or fall back: delete the var, use "Custom Start Command" in Settings to force the celery command.
- Worker crashes at boot → missing `DATABASE_URL` / `REDIS_URL` / `OPENROUTER_API_KEY`
- Tasks firing twice → beat replicas > 1
- Beat schedule resets on restart → expected (ephemeral disk); switch to RedBeat / DatabaseScheduler if persistence needed

## Rollback
Delete `NIXPACKS_CONFIG_FILE` on worker/beat — they revert to the shared `nixpacks.toml`. Slower builds but functional.
