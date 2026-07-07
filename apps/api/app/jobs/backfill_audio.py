"""One-time audio backfill for enriched vocab items missing word audio.

Run from apps/api: uv run python -m app.jobs.backfill_audio [--batch-size N]
"""

from __future__ import annotations

import argparse
import asyncio

from app.jobs.content_gen import backfill_audio


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--batch-size", type=int, default=100)
    args = parser.parse_args()
    result = asyncio.run(backfill_audio(batch_size=args.batch_size))
    print(f"done: {result['rendered']} rendered, {result['skipped']} skipped")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
