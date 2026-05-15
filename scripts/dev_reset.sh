#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")"/.. && pwd)"
API_DIR="$ROOT_DIR/apps/api"

if [ ! -e "$API_DIR/.env" ]; then
  ln -s "$ROOT_DIR/.env" "$API_DIR/.env"
fi

echo "Running migrations..."
cd "$API_DIR"
uv run alembic upgrade head

echo "Seeding vocab + dev user..."
uv run python -m scripts.seed_vocab \
  "$API_DIR/scripts/seed_examples.json" \
  --create-reviews-for dev@example.com \
  --ensure-user \
  --user-name "Dev"

cd "$ROOT_DIR"
echo "Done."
