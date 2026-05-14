import logging
from typing import TypeVar

from openai import OpenAI
from openai.types.chat import ChatCompletionMessageParam
from pydantic import ValidationError

from app.core.config import get_settings
from app.schemas.llm import LLMOutput

T = TypeVar("T", bound=LLMOutput)

logger = logging.getLogger(__name__)


class LLMValidationFailure(Exception):
    def __init__(self, message: str, attempts: int, last_error: ValidationError | None) -> None:
        super().__init__(message)
        self.attempts = attempts
        self.last_error = last_error


class LLMClient:
    def __init__(
        self,
        *,
        openai_client: OpenAI | None = None,
        model: str | None = None,
        timeout_s: float = 30.0,
        max_tokens: int = 1000,
    ) -> None:
        settings = get_settings()
        self._client = openai_client or OpenAI(
            base_url=settings.llm_base_url,
            api_key=settings.llm_api_key.get_secret_value(),
        )
        self._model = model or settings.llm_model
        self._timeout_s = timeout_s
        self._max_tokens = max_tokens

    def complete(self, prompt: str, response_schema: type[T], max_retries: int = 3) -> T:
        messages: list[ChatCompletionMessageParam] = [{"role": "user", "content": prompt}]
        last_error: ValidationError | None = None

        for attempt in range(1, max_retries + 1):
            completion = self._client.chat.completions.create(
                model=self._model,
                messages=messages,
                response_format={"type": "json_object"},
                timeout=self._timeout_s,
                max_tokens=self._max_tokens,
            )
            usage = completion.usage
            logger.info(
                "llm_call",
                extra={
                    "model": self._model,
                    "prompt_tokens": usage.prompt_tokens if usage else 0,
                    "completion_tokens": usage.completion_tokens if usage else 0,
                    "attempt": attempt,
                },
            )
            content = completion.choices[0].message.content or ""

            try:
                return response_schema.model_validate_json(content)
            except ValidationError as e:
                last_error = e
                logger.warning(
                    "llm_validation_failed",
                    extra={"attempt": attempt, "errors": e.errors()},
                )
                messages.append({"role": "assistant", "content": content})
                messages.append({"role": "user", "content": _refinement_message(e)})

        raise LLMValidationFailure(
            f"validation failed after {max_retries} attempts",
            attempts=max_retries,
            last_error=last_error,
        )


def _refinement_message(error: ValidationError) -> str:
    lines = ["Your previous response failed validation. Please fix and resend valid JSON only."]
    for err in error.errors():
        loc = ".".join(str(p) for p in err["loc"])
        lines.append(f"- field `{loc}`: {err['msg']}")
    return "\n".join(lines)
