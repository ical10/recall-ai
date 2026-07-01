from __future__ import annotations

import logging
import time
from abc import ABC, abstractmethod
from collections.abc import Callable

from app.core.config import get_settings
from app.models.vocab_item import VocabItem

logger = logging.getLogger(__name__)

RENDER_TIMEOUT_S = 30
MAX_RETRIES = 2


class TTSEngine(ABC):
    @abstractmethod
    def synthesize(self, text: str, voice: str) -> bytes: ...


class GeminiEngine(TTSEngine):
    def synthesize(self, text: str, voice: str) -> bytes:
        from google.genai import Client

        settings = get_settings()
        key = settings.voice_agent_api_key.get_secret_value()
        client = Client(api_key=key)
        response = client.models.generate_content(
            model="gemini-2.5-flash-preview-tts",
            contents=text,
            config={"voice": voice},  # type: ignore[arg-type]
        )
        return response.audio.data  # type: ignore[no-any-return,attr-defined]


class SpeechifyEngine(TTSEngine):
    def synthesize(self, text: str, voice: str) -> bytes:
        import requests

        settings = get_settings()
        api_key = settings.voice_agent_api_key.get_secret_value()
        resp = requests.post(
            "https://api.speechify.ai/v1/audio/speech",
            headers={"Authorization": f"Bearer {api_key}"},
            json={
                "input": text,
                "voice_id": voice,
                "audio_format": "mp3",
            },
            timeout=RENDER_TIMEOUT_S,
        )
        if not resp.ok:
            raise RuntimeError(f"Speechify {resp.status_code}: {resp.text[:300]}")
        data = resp.json()
        audio_url = data["audio_data"]
        audio_resp = requests.get(audio_url, timeout=RENDER_TIMEOUT_S)
        if not audio_resp.ok:
            raise RuntimeError(f"Speechify audio download {audio_resp.status_code}")
        return audio_resp.content


_ENGINES: dict[str, TTSEngine] = {
    "gemini": GeminiEngine(),
    "speechify": SpeechifyEngine(),
}


def _upload_to_r2(key: str, data: bytes, content_type: str = "audio/mpeg") -> str:
    settings = get_settings()
    if not settings.r2_endpoint:
        return ""
    # lazy import: keep the boto3 SDK out of every worker/beat process's baseline RSS
    import boto3  # type: ignore[import-untyped]

    s3 = boto3.client(
        "s3",
        endpoint_url=settings.r2_endpoint,
        aws_access_key_id=settings.r2_access_key_id,
        aws_secret_access_key=settings.r2_secret_access_key.get_secret_value(),
    )
    s3.put_object(
        Bucket=settings.r2_bucket,
        Key=key,
        Body=data,
        ContentType=content_type,
    )
    return f"{settings.r2_public_url.rstrip('/')}/{key}"


def synthesize(text: str, *, voice: str | None = None) -> str:
    settings = get_settings()
    provider = settings.voice_agent_provider
    if not provider or not text.strip():
        return ""

    voice = voice or settings.voice_agent_model
    engine = _ENGINES.get(provider)
    if engine is None:
        logger.warning("tts_unknown_provider", extra={"provider": provider})
        return ""

    char_count = len(text)
    start = time.monotonic()
    for attempt in range(1 + MAX_RETRIES):
        try:
            audio_bytes = engine.synthesize(text, voice)
            elapsed = time.monotonic() - start
            logger.info(
                "tts_synthesized",
                extra={
                    "provider": provider,
                    "chars": char_count,
                    "bytes": len(audio_bytes),
                    "attempts": attempt + 1,
                    "elapsed_s": round(elapsed, 2),
                },
            )
            return _upload_to_r2(f"audio/{hash(text) & 0xFFFFFFFFFF}.mp3", audio_bytes)
        except Exception as e:
            logger.warning(
                "tts_attempt_failed",
                extra={
                    "provider": provider,
                    "attempt": attempt + 1,
                    "chars": char_count,
                    "error": str(e)[:200],
                },
            )
            if attempt == MAX_RETRIES:
                logger.error("tts_exhausted", extra={"chars": char_count})
                return ""
    return ""


def ensure_audio(vocab: VocabItem, *, synth: Callable[[str], str] = synthesize) -> bool:
    """Render any missing audio clips for one Vocab Item, idempotently.

    The single home for the skip-if-already-rendered guard: synthesizes only the
    clips whose URL is unset, mutates `vocab` in place, and returns True if anything
    was rendered. No DB commit — the caller owns the transaction.
    """
    rendered = False
    if not vocab.word_audio_url:
        url = synth(vocab.token)
        if url:
            vocab.word_audio_url = url
            rendered = True
    if not vocab.example_audio_url:
        url = synth(vocab.example_sentence or "")
        if url:
            vocab.example_audio_url = url
            rendered = True
    return rendered
