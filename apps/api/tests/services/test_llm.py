import json
from unittest.mock import MagicMock

import pytest
from openai.types.chat import ChatCompletion, ChatCompletionMessage
from openai.types.chat.chat_completion import Choice
from openai.types.completion_usage import CompletionUsage
from pydantic import ValidationError

from app.schemas.llm import GeneratedVocabBatch, LLMOutput, SimpleVocabExample
from app.services.llm import LLMClient, LLMValidationFailure


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


def test_simple_vocab_example_rejects_token_appearing_only_as_substring() -> None:
    # `cat` should not be considered "in" `concatenation` — must match as a whole word.
    with pytest.raises(ValidationError):
        SimpleVocabExample(
            token="cat",
            definition="A small domesticated carnivorous mammal.",
            example="String concatenation is a common operation.",
        )


def test_generated_vocab_batch_validates_list_of_items() -> None:
    batch = GeneratedVocabBatch(
        items=[
            SimpleVocabExample(
                token="ephemeral",
                definition="Lasting briefly; transient and short-lived.",
                example="The cherry blossoms were ephemeral but unforgettable.",
            ),
        ]
    )
    assert len(batch.items) == 1
    assert batch.items[0].token == "ephemeral"


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
    assert call_kwargs["max_tokens"] == 1000


def test_complete_passes_overridden_max_tokens_to_provider() -> None:
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

    client = LLMClient(
        openai_client=fake_openai, model="test-model", timeout_s=10.0, max_tokens=250
    )
    client.complete("Define ephemeral.", SimpleVocabExample)

    call_kwargs = fake_openai.chat.completions.create.call_args.kwargs
    assert call_kwargs["max_tokens"] == 250


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

    log_records = [
        r for r in caplog.records if r.name == "app.services.llm" and r.levelname == "INFO"
    ]
    assert any(
        getattr(r, "prompt_tokens", None) == 123 and getattr(r, "completion_tokens", None) == 45
        for r in log_records
    )


def test_complete_retries_with_refined_prompt_on_validation_failure() -> None:
    fake_openai = MagicMock()
    fake_openai.chat.completions.create.side_effect = [
        _fake_completion(json.dumps({"token": "ephemeral"})),
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

    second_messages = fake_openai.chat.completions.create.call_args_list[1].kwargs["messages"]
    refinement = second_messages[-1]["content"]
    assert "previous response failed validation" in refinement.lower()
    assert "definition" in refinement or "example" in refinement


def test_complete_raises_after_max_retries_exhausted() -> None:
    fake_openai = MagicMock()
    fake_openai.chat.completions.create.return_value = _fake_completion(json.dumps({"token": "x"}))
    client = LLMClient(openai_client=fake_openai, model="test-model", timeout_s=10.0)

    with pytest.raises(LLMValidationFailure) as excinfo:
        client.complete("Define x.", SimpleVocabExample, max_retries=3)

    assert excinfo.value.attempts == 3
    assert fake_openai.chat.completions.create.call_count == 3


def test_llm_client_defaults_to_openai_constructed_from_settings(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.core.config import Settings
    from app.services import llm as llm_module

    fake_settings = Settings(
        database_url="x",
        redis_url="x",
        llm_api_key="sk-test-real",
        secret_key="x",
        llm_model="some/model:free",
        llm_base_url="https://example.test/api/v1",
        google_redirect_uri="http://localhost:8000/auth/callback",
    )
    monkeypatch.setattr(llm_module, "get_settings", lambda: fake_settings)

    captured: dict[str, object] = {}

    class FakeOpenAI:
        def __init__(self, *, base_url: str, api_key: str) -> None:
            captured["base_url"] = base_url
            captured["api_key"] = api_key

    monkeypatch.setattr(llm_module, "OpenAI", FakeOpenAI)

    client = LLMClient()

    assert captured == {"base_url": "https://example.test/api/v1", "api_key": "sk-test-real"}
    assert client._model == "some/model:free"


def test_complete_includes_system_prompt_as_first_message_when_provided() -> None:
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
    client.complete(
        "Define ephemeral.",
        SimpleVocabExample,
        system_prompt="You are a vocabulary curator.",
    )

    messages = fake_openai.chat.completions.create.call_args.kwargs["messages"]
    assert messages[0] == {"role": "system", "content": "You are a vocabulary curator."}
    assert messages[1]["role"] == "user"
    assert messages[1]["content"] == "Define ephemeral."


def test_complete_system_prompt_persists_across_refinement_retries() -> None:
    fake_openai = MagicMock()
    fake_openai.chat.completions.create.side_effect = [
        _fake_completion(json.dumps({"token": "x"})),
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
    client.complete(
        "Define ephemeral.",
        SimpleVocabExample,
        max_retries=3,
        system_prompt="You are a curator.",
    )

    first_messages = fake_openai.chat.completions.create.call_args_list[0].kwargs["messages"]
    second_messages = fake_openai.chat.completions.create.call_args_list[1].kwargs["messages"]
    assert first_messages[0] == {"role": "system", "content": "You are a curator."}
    assert second_messages[0] == {"role": "system", "content": "You are a curator."}


def test_complete_per_call_max_tokens_overrides_instance_default() -> None:
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
    client = LLMClient(
        openai_client=fake_openai, model="test-model", timeout_s=10.0, max_tokens=100
    )
    client.complete("Define ephemeral.", SimpleVocabExample, max_tokens=4096)

    call_kwargs = fake_openai.chat.completions.create.call_args.kwargs
    assert call_kwargs["max_tokens"] == 4096


def test_complete_logs_attempt_number_on_each_call(caplog: pytest.LogCaptureFixture) -> None:
    import logging

    fake_openai = MagicMock()
    fake_openai.chat.completions.create.return_value = _fake_completion(json.dumps({"token": "x"}))
    client = LLMClient(openai_client=fake_openai, model="test-model", timeout_s=10.0)

    with (
        caplog.at_level(logging.INFO, logger="app.services.llm"),
        pytest.raises(LLMValidationFailure),
    ):
        client.complete("Define x.", SimpleVocabExample, max_retries=3)

    attempts = [
        getattr(r, "attempt", None)
        for r in caplog.records
        if r.name == "app.services.llm" and r.levelname == "INFO"
    ]
    assert attempts == [1, 2, 3]
