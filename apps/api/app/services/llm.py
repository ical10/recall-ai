import logging
from typing import TypeVar

from openai import OpenAI

from app.schemas.llm import LLMOutput

T = TypeVar("T", bound=LLMOutput)

logger = logging.getLogger(__name__)


class LLMValidationFailure(Exception):
    pass


class LLMClient:
    def __init__(
        self,
        *,
        openai_client: OpenAI | None = None,
        model: str | None = None,
        timeout_s: float = 30.0,
    ) -> None:
        self._client = openai_client
        self._model = model
        self._timeout_s = timeout_s

    def complete(self, prompt: str, response_schema: type[T], max_retries: int = 3) -> T:
        assert self._client is not None
        completion = self._client.chat.completions.create(
            model=self._model or "",
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
            timeout=self._timeout_s,
        )
        usage = completion.usage
        logger.info(
            "llm_call",
            extra={
                "model": self._model,
                "prompt_tokens": usage.prompt_tokens if usage else 0,
                "completion_tokens": usage.completion_tokens if usage else 0,
                "attempt": 1,
            },
        )
        content = completion.choices[0].message.content or ""
        return response_schema.model_validate_json(content)
