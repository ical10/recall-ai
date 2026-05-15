#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")"/.. && pwd)"

cd "$ROOT_DIR"

echo "Running migrations..."
uv run alembic upgrade head

echo "Seeding vocab + dev user..."
uv run python -m scripts.seed_vocab \
  apps/api/scripts/seed_examples.json \
  --create-reviews-for dev@example.com \
  --ensure-user \
  --user-name "Dev"

echo "Done."
