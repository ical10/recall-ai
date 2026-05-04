# LLM Client + Retry-with-Prompt-Refinement Harness Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a thin, typed wrapper around the OpenAI SDK (pointed at OpenRouter) that takes a pydantic output schema, calls the model with structured-output mode, validates the response, retries with prompt refinement on validation failure, logs token cost on every call, and respects a hard timeout.

**Architecture:** A single `LLMClient` class instantiated per process from `Settings`. The public method is `complete[T: BaseModel](prompt: str, response_schema: type[T], max_retries: int = 3) -> T`. Internally: build messages → call `client.chat.completions.create(..., response_format={"type": "json_object"})` → parse JSON → validate via `response_schema.model_validate_json` → on `ValidationError`, log + append a refinement clause naming the failed constraints + retry. After `max_retries` failures, raise `LLMValidationFailure` with the last error and accumulated token cost. All calls log structured: model, prompt-token count, completion-token count, attempt number, validation outcome.

**Tech Stack:** `openai>=2.0,<3` (already a dep), pydantic v2, Python `logging` (structured via `extra=`), `unittest.mock` for tests.

---

## File Structure

**Create:**
- `apps/api/app/services/llm.py` — `LLMClient`, `LLMValidationFailure` exception, internal helpers
- `apps/api/app/schemas/llm.py` — base + one example concrete schema (`SimpleVocabExample` for self-test)
- `apps/api/tests/services/__init__.py` — package marker (skip if SM-2 plan already created it)
- `apps/api/tests/services/test_llm.py` — mocked OpenAI client tests

**Modify:**
- `apps/api/app/schemas/__init__.py` — re-export the new schemas

**No edits to:** `app/main.py`, `app/core/`, templates, settings.

---

## Background: How OpenRouter and structured outputs interact

OpenRouter exposes the OpenAI Chat Completions API. The OpenAI Python SDK works as the client when configured with `base_url=settings.openrouter_base_url` and `api_key=settings.openrouter_api_key`. The `response_format={"type": "json_object"}` parameter is best-effort across OpenRouter models — strong models honor it, weak free models do not. **Pydantic validation at our boundary is the source of truth, not the SDK's mode flag.**

This is exactly why the retry-with-refinement loop exists: we don't trust the model to produce valid JSON-of-the-right-shape, we re-prompt with the specific failure spelled out.

---

## Task 1: Add the schemas (TDD)

- [ ] **Step 1**: Create `apps/api/tests/services/__init__.py` if it doesn't exist (empty).

- [ ] **Step 2**: Create `apps/api/tests/services/test_llm.py` with the schema-only tests:

```python
import pytest
from pydantic import ValidationError

from app.schemas.llm import LLMOutput, SimpleVocabExample


def test_llm_output_is_a_base_class() -> None:
    # LLMOutput is a generic base class for all LLM-produced pydantic models.
    # We can't instantiate it directly because it has no fields of its own,
    # but subclasses inherit from it.
    assert issubclass(SimpleVocabExample, LLMOutput)


def test_simple_vocab_example_validates_required_fields() -> None:
    obj = SimpleVocabExample(token="ephemeral", definition="Lasting briefly.", example="The mood was ephemeral.")
    assert obj.token == "ephemeral"
    assert obj.definition == "Lasting briefly."


def test_simple_vocab_example_rejects_short_definition() -> None:
    with pytest.raises(ValidationError):
        SimpleVocabExample(token="x", definition="too short", example="...")


def test_simple_vocab_example_rejects_example_missing_token() -> None:
    # Custom validator: the example sentence must contain the target token.
    with pytest.raises(ValidationError):
        SimpleVocabExample(
            token="ephemeral",
            definition="A definition that meets the minimum length.",
            example="A sentence that does not include the word.",
        )
```

- [ ] **Step 3**: Run; fail with `ModuleNotFoundError`.

- [ ] **Step 4**: Implement `apps/api/app/schemas/llm.py`:

```python
from pydantic import BaseModel, Field, model_validator


class LLMOutput(BaseModel):
    """Base class for every pydantic schema we ask an LLM to produce.

    Inheriting marks a schema as LLM-bound and lets the client treat them
    uniformly for refinement-prompt construction.
    """

    model_config = {"extra": "forbid"}


class SimpleVocabExample(LLMOutput):
    token: str = Field(min_length=1, max_length=64)
    definition: str = Field(min_length=20, max_length=500)
    example: str = Field(min_length=10, max_length=500)

    @model_validator(mode="after")
    def _example_must_contain_token(self) -> "SimpleVocabExample":
        if self.token.lower() not in self.example.lower():
            raise ValueError("example sentence must contain the target token")
        return self
```

- [ ] **Step 5**: Run; tests pass.

- [ ] **Step 6**: Update `apps/api/app/schemas/__init__.py` to re-export — append:

```python
from app.schemas.llm import LLMOutput, SimpleVocabExample
```

(adjust `__all__` accordingly)

- [ ] **Step 7**: Commit — `feat: add LLMOutput base + SimpleVocabExample schema with custom validator`.

---

## Task 2: LLMClient happy path (TDD)

- [ ] **Step 1**: Append to `test_llm.py`:

```python
import json
from unittest.mock import MagicMock

from openai.types.chat import ChatCompletion, ChatCompletionMessage
from openai.types.chat.chat_completion import Choice
from openai.types.completion_usage import CompletionUsage

from app.services.llm import LLMClient, LLMValidationFailure


def _fake_completion(content: str, prompt_tokens: int = 100, completion_tokens: int = 50) -> ChatCompletion:
    return ChatCompletion(
        id="cmpl-test",
        choices=[
            Choice(
                index=0,
                finish_reason="stop",
                message=ChatCompletionMessage(role="assistant", content=content),
            )
        ],
        created=0,
        model="test-model",
        object="chat.completion",
        usage=CompletionUsage(
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=prompt_tokens + completion_tokens,
        ),
    )


def test_complete_returns_validated_pydantic_object_on_first_try() -> None:
    fake_openai = MagicMock()
    fake_openai.chat.completions.create.return_value = _fake_completion(
        json.dumps(
            {
                "token": "ephemeral",
                "definition": "Lasting briefly; transient and short-lived.",
                "example": "The cherry blossoms were ephemeral but unforgettable.",
            }
        )
    )

    client = LLMClient(openai_client=fake_openai, model="test-model", timeout_s=10.0)
    result = client.complete("Define ephemeral.", SimpleVocabExample)

    assert isinstance(result, SimpleVocabExample)
    assert result.token == "ephemeral"
    fake_openai.chat.completions.create.assert_called_once()
    call_kwargs = fake_openai.chat.completions.create.call_args.kwargs
    assert call_kwargs["model"] == "test-model"
    assert call_kwargs["timeout"] == 10.0
    assert call_kwargs["response_format"] == {"type": "json_object"}


def test_complete_logs_token_usage(caplog) -> None:
    import logging

    fake_openai = MagicMock()
    fake_openai.chat.completions.create.return_value = _fake_completion(
        json.dumps(
            {
                "token": "ephemeral",
                "definition": "Lasting briefly; transient and short-lived.",
                "example": "The cherry blossoms were ephemeral but unforgettable.",
            }
        ),
        prompt_tokens=123,
        completion_tokens=45,
    )
    client = LLMClient(openai_client=fake_openai, model="test-model", timeout_s=10.0)

    with caplog.at_level(logging.INFO, logger="app.services.llm"):
        client.complete("Define ephemeral.", SimpleVocabExample)

    log_records = [r for r in caplog.records if r.levelname == "INFO"]
    assert any(
        getattr(r, "prompt_tokens", None) == 123 and getattr(r, "completion_tokens", None) == 45
        for r in log_records
    )
```

- [ ] **Step 2**: Run; fail with `ModuleNotFoundError`.

- [ ] **Step 3**: Implement `apps/api/app/services/llm.py` (happy path only — retry path lands in next task):

```python
import logging
from typing import TypeVar

from openai import OpenAI
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
    ) -> None:
        settings = get_settings()
        self._client = openai_client or OpenAI(
            base_url=settings.openrouter_base_url,
            api_key=settings.openrouter_api_key,
        )
        self._model = model or settings.llm_model
        self._timeout_s = timeout_s

    def complete(self, prompt: str, response_schema: type[T], max_retries: int = 3) -> T:
        messages = [{"role": "user", "content": prompt}]
        completion = self._client.chat.completions.create(
            model=self._model,
            messages=messages,
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
        try:
            return response_schema.model_validate_json(content)
        except ValidationError as e:
            raise LLMValidationFailure(
                f"validation failed after 1 attempt", attempts=1, last_error=e
            ) from e
```

- [ ] **Step 4**: Run; happy-path tests pass.

- [ ] **Step 5**: Commit — `feat: add LLMClient happy-path with timeout, json_object mode, token logging`.

---

## Task 3: Retry-with-prompt-refinement (TDD)

- [ ] **Step 1**: Append:

```python
def test_complete_retries_with_refined_prompt_on_validation_failure() -> None:
    fake_openai = MagicMock()
    fake_openai.chat.completions.create.side_effect = [
        # Attempt 1: malformed JSON (missing required field)
        _fake_completion(json.dumps({"token": "ephemeral"})),
        # Attempt 2: valid
        _fake_completion(
            json.dumps(
                {
                    "token": "ephemeral",
                    "definition": "Lasting briefly; transient and short-lived.",
                    "example": "The cherry blossoms were ephemeral but unforgettable.",
                }
            )
        ),
    ]

    client = LLMClient(openai_client=fake_openai, model="test-model", timeout_s=10.0)
    result = client.complete("Define ephemeral.", SimpleVocabExample, max_retries=3)

    assert isinstance(result, SimpleVocabExample)
    assert fake_openai.chat.completions.create.call_count == 2

    # Second call's user message must include the refinement clause.
    second_messages = fake_openai.chat.completions.create.call_args_list[1].kwargs["messages"]
    refinement = second_messages[-1]["content"]
    assert "previous response failed validation" in refinement.lower()
    assert "definition" in refinement or "example" in refinement


def test_complete_raises_after_max_retries_exhausted() -> None:
    fake_openai = MagicMock()
    fake_openai.chat.completions.create.return_value = _fake_completion(
        json.dumps({"token": "x"})
    )
    client = LLMClient(openai_client=fake_openai, model="test-model", timeout_s=10.0)

    with pytest.raises(LLMValidationFailure) as excinfo:
        client.complete("Define x.", SimpleVocabExample, max_retries=3)

    assert excinfo.value.attempts == 3
    assert fake_openai.chat.completions.create.call_count == 3


def test_complete_logs_attempt_number_on_each_call(caplog) -> None:
    import logging

    fake_openai = MagicMock()
    fake_openai.chat.completions.create.return_value = _fake_completion(json.dumps({"token": "x"}))
    client = LLMClient(openai_client=fake_openai, model="test-model", timeout_s=10.0)

    with caplog.at_level(logging.INFO, logger="app.services.llm"), pytest.raises(LLMValidationFailure):
        client.complete("Define x.", SimpleVocabExample, max_retries=3)

    attempts = [getattr(r, "attempt", None) for r in caplog.records if r.levelname == "INFO"]
    assert attempts == [1, 2, 3]
```

- [ ] **Step 2**: Run; failure tests fail (current code only does one attempt).

- [ ] **Step 3**: Replace `complete` in `apps/api/app/services/llm.py`:

```python
def complete(self, prompt: str, response_schema: type[T], max_retries: int = 3) -> T:
    messages: list[dict[str, str]] = [{"role": "user", "content": prompt}]
    last_error: ValidationError | None = None

    for attempt in range(1, max_retries + 1):
        completion = self._client.chat.completions.create(
            model=self._model,
            messages=messages,
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
            messages.append(
                {
                    "role": "user",
                    "content": _refinement_message(e),
                }
            )

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
```

- [ ] **Step 4**: Run; all tests pass.

- [ ] **Step 5**: Commit — `feat: add retry-with-prompt-refinement loop to LLMClient`.

---

## Task 4: Final verification

- [ ] **Step 1**: Run full suite — confirm everything green.
- [ ] **Step 2**: Run `pnpm lint` — ruff + mypy strict — must pass. The pydantic.mypy plugin (already configured) handles `LLMOutput` subclasses.
- [ ] **Step 3**: No commit needed for verification.

---

## Out of Scope

- Async client (`AsyncOpenAI`) — Celery workers are sync-only per CLAUDE.md, and route handlers that need LLM calls will dispatch to Celery anyway. Add an async variant only when an async route demonstrably needs it.
- Streaming
- Tool/function calling
- Embeddings, image inputs, audio
- Cost-in-USD calculation — token logging is sufficient; cost can be derived from logs by an external aggregator
- Caching of identical prompts — wait for evidence we hit duplicates often enough to matter

## Risks

- **Token-count assertions in tests rely on `extra=` log fields** — the test harness uses `caplog.records[i].prompt_tokens`, which works because Python logging makes `extra` fields attributes on the LogRecord. If the project later swaps to structlog, these assertions need updating.
- **`response_format={"type": "json_object"}` is best-effort on free OpenRouter models** — that's the entire reason for the retry loop. Validate carefully when picking a dev model: `meta-llama/llama-3.3-70b-instruct:free` honors it more often than smaller free models.
- **`OpenAI()` instantiation at module import time would block on missing API key** — `LLMClient.__init__` only constructs the client when called, so importing the module is safe. Tests inject a `MagicMock` and don't trigger the real constructor.
