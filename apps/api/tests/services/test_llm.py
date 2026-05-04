import pytest
from pydantic import ValidationError

from app.schemas.llm import LLMOutput, SimpleVocabExample


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
