import json
from unittest.mock import MagicMock

import pytest
from openai.types.chat import ChatCompletion, ChatCompletionMessage
from openai.types.chat.chat_completion import Choice
from openai.types.completion_usage import CompletionUsage
from pydantic import ValidationError

from app.schemas.llm import LLMOutput, SimpleVocabExample
from app.services.llm import LLMClient


def _fake_completion(
    content: str, prompt_tokens: int = 100, completion_tokens: int = 50
) -> ChatCompletion:
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


def test_llm_output_is_a_base_class() -> None:
    assert issubclass(SimpleVocabExample, LLMOutput)


def test_simple_vocab_example_validates_required_fields() -> None:
    obj = SimpleVocabExample(
        token="ephemeral",
        definition="Lasting briefly; transient and short-lived.",
        example="The mood was ephemeral.",
    )
    assert obj.token == "ephemeral"
    assert obj.definition == "Lasting briefly; transient and short-lived."


def test_simple_vocab_example_rejects_short_definition() -> None:
    with pytest.raises(ValidationError):
        SimpleVocabExample(token="x", definition="too short", example="...")


def test_simple_vocab_example_rejects_example_missing_token() -> None:
    with pytest.raises(ValidationError):
        SimpleVocabExample(
            token="ephemeral",
            definition="A definition that meets the minimum length.",
            example="A sentence that does not include the word.",
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


def test_complete_logs_token_usage(caplog: pytest.LogCaptureFixture) -> None:
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
