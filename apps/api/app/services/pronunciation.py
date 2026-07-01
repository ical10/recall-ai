from __future__ import annotations

import json
import logging
import time
from abc import ABC, abstractmethod

from app.core.config import get_settings
from app.schemas.pronunciation import PronunciationVerdict

logger = logging.getLogger(__name__)

EVAL_MAX_RETRIES = 2
EVAL_TIMEOUT_S = 15

_PROMPT = (
    "Did the speaker say the English word '{target}'? Reply with JSON only:\n"
    '{{"said_target": true|false, "heard": "what you heard", '
    '"confidence": 0.0-1.0, '
    '"feedback": "short, kind, kid-friendly message (max 200 chars)"}}\n'
    "If the child said the word correctly (even with an accent), said_target must be true."
)


class PronunciationEngine(ABC):
    @abstractmethod
    def evaluate(self, audio: bytes, mime_type: str, *, target: str) -> str: ...


class GeminiPronunciationEngine(PronunciationEngine):
    def evaluate(self, audio: bytes, mime_type: str, *, target: str) -> str:
        from google.genai import Client
        from google.genai.types import GenerateContentConfig

        settings = get_settings()
        client = Client(api_key=settings.stt_api_key.get_secret_value())
        from google.genai.types import Part

        prompt = _PROMPT.format(target=target)
        audio_part = Part.from_bytes(data=audio, mime_type=mime_type)
        response = client.models.generate_content(
            model=settings.stt_model,
            contents=[audio_part, prompt],
            config=GenerateContentConfig(response_mime_type="application/json"),
        )
        return response.text or ""


_ENGINES: dict[str, PronunciationEngine] = {
    "gemini": GeminiPronunciationEngine(),
}


def evaluate_pronunciation(
    audio: bytes,
    mime_type: str,
    *,
    target: str,
) -> PronunciationVerdict:
    settings = get_settings()
    provider = settings.stt_provider
    if not provider:
        raise RuntimeError("No STT provider configured")

    engine = _ENGINES.get(provider)
    if engine is None:
        raise RuntimeError(f"Unknown STT provider: {provider}")

    start = time.monotonic()
    last_error: Exception | None = None

    for attempt in range(1 + EVAL_MAX_RETRIES):
        try:
            raw = engine.evaluate(audio, mime_type, target=target)
            elapsed = time.monotonic() - start

            try:
                cleaned = raw.strip()
                if cleaned.startswith("```"):
                    cleaned = cleaned.split("\n", 1)[1] if "\n" in cleaned else cleaned[3:]
                if cleaned.endswith("```"):
                    cleaned = cleaned[: cleaned.rfind("```")].strip()
                data = json.loads(cleaned)
            except json.JSONDecodeError:
                last_error = ValueError("invalid JSON from engine")
                continue

            verdict = PronunciationVerdict.model_validate(data)
            logger.info(
                "pronunciation_eval",
                extra={
                    "provider": provider,
                    "target": target,
                    "bytes": len(audio),
                    "attempts": attempt + 1,
                    "latency_s": round(elapsed, 2),
                    "said_target": verdict.said_target,
                    "confidence": verdict.confidence,
                },
            )
            return verdict

        except Exception as e:
            last_error = e
            logger.warning(
                "pronunciation_eval_attempt_failed",
                extra={"attempt": attempt + 1, "error": str(e)[:200]},
            )

    raise RuntimeError(f"Pronunciation evaluation exhausted: {last_error}")
