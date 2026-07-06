"""One-time generator for starter-vocab word audio.

Run from the repo root: uv run python apps/api/scripts/generate_starter_audio.py
Reads VOICE_AGENT_API_KEY via the app's normal Settings/.env loading — use the
prod Speechify key.

Speechify on purpose (not the configured VOICE_AGENT_PROVIDER): it matches the
nightly pipeline's voice so every word sounds like one speaker, and it is the
only engine verified to return mp3 bytes.
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT / "apps" / "api"))

SPEECHIFY_MODEL = "simba-english"
OUT_DIR = REPO_ROOT / "apps" / "web" / "public" / "audio" / "starter"


def main() -> int:
    from app.services.account import STARTER_VOCAB
    from app.services.tts import SpeechifyEngine

    engine = SpeechifyEngine()
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    written = 0
    for entry in STARTER_VOCAB:
        token = entry["token"]
        out = OUT_DIR / f"{token}.mp3"
        if out.exists():
            print(f"skip {out.name} (exists)")
            continue
        audio = engine.synthesize(token, SPEECHIFY_MODEL)
        out.write_bytes(audio)
        print(f"wrote {out.name} ({len(audio)} bytes)")
        written += 1

    print(f"done: {written} written, {len(STARTER_VOCAB) - written} skipped")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
