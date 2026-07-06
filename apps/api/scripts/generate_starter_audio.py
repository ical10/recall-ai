"""One-time generator for starter-vocab word audio.

Run from the repo root: uv run python apps/api/scripts/generate_starter_audio.py
Reads only VOICE_AGENT_API_KEY from .env — use the prod Speechify key.

Speechify on purpose (not the configured VOICE_AGENT_PROVIDER): it matches the
nightly pipeline's voice so every word sounds like one speaker, and it is the
only engine verified to return mp3 bytes.
"""

from __future__ import annotations

import base64
import sys
from pathlib import Path

import requests

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT / "apps" / "api"))

SPEECHIFY_MODEL = "simba-english"
OUT_DIR = REPO_ROOT / "apps" / "web" / "public" / "audio" / "starter"


def read_api_key() -> str:
    for line in (REPO_ROOT / ".env").read_text().splitlines():
        if line.startswith("VOICE_AGENT_API_KEY="):
            return line.split("=", 1)[1].strip().strip('"')
    raise SystemExit("VOICE_AGENT_API_KEY not found in .env")


def synthesize(api_key: str, text: str) -> bytes:
    resp = requests.post(
        "https://api.speechify.ai/v1/audio/speech",
        headers={"Authorization": f"Bearer {api_key}"},
        json={
            "input": text,
            "voice_id": "george",
            "audio_format": "mp3",
            "model": SPEECHIFY_MODEL,
        },
        timeout=30,
    )
    if not resp.ok:
        raise RuntimeError(f"Speechify {resp.status_code}: {resp.text[:300]}")
    return base64.b64decode(resp.json()["audio_data"])


def main() -> int:
    from app.services.account import STARTER_VOCAB

    api_key = read_api_key()
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    written = 0
    for entry in STARTER_VOCAB:
        token = entry["token"]
        out = OUT_DIR / f"{token}.mp3"
        if out.exists():
            print(f"skip {out.name} (exists)")
            continue
        audio = synthesize(api_key, token)
        out.write_bytes(audio)
        print(f"wrote {out.name} ({len(audio)} bytes)")
        written += 1

    print(f"done: {written} written, {len(STARTER_VOCAB) - written} skipped")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
