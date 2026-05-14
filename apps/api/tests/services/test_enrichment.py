import uuid
from datetime import UTC, datetime
from unittest.mock import MagicMock

import pytest

from app.models.vocab_item import VocabItem
from app.schemas.llm import SimpleVocabExample
from app.services.enrichment import enrich_vocab_item
from app.services.llm import LLMClient, LLMValidationFailure


def _vocab_item(token: str = "ephemeral", language: str = "en") -> VocabItem:
    now = datetime.now(UTC)
    item = VocabItem(
        id=uuid.uuid4(),
        token=token,
        language=language,
        definition="",
    )
    item.created_at = now
    item.updated_at = now
    return item


def test_enrich_vocab_item_calls_llm_with_token_and_language() -> None:
    item = _vocab_item(token="ephemeral", language="en")
    mock_llm = MagicMock(spec=LLMClient)
    mock_llm.complete.return_value = SimpleVocabExample(
        token="ephemeral",
        definition="Lasting briefly; transient and short-lived in nature.",
        example="The cherry blossoms were ephemeral but stunning.",
    )

    enrich_vocab_item(item, mock_llm)

    call_args = mock_llm.complete.call_args
    prompt: str = call_args[0][0]
    assert "ephemeral" in prompt
    assert "en" in prompt


def test_enrich_vocab_item_returns_validated_simple_vocab_example() -> None:
    item = _vocab_item(token="fleeting", language="en")
    expected = SimpleVocabExample(
        token="fleeting",
        definition="Passing swiftly; lasting only a short time.",
        example="It was a fleeting moment of joy.",
    )
    mock_llm = MagicMock(spec=LLMClient)
    mock_llm.complete.return_value = expected

    result = enrich_vocab_item(item, mock_llm)

    assert result is expected
    assert isinstance(result, SimpleVocabExample)


def test_enrich_vocab_item_propagates_llm_validation_failure() -> None:
    item = _vocab_item(token="fleeting", language="en")
    mock_llm = MagicMock(spec=LLMClient)
    mock_llm.complete.side_effect = LLMValidationFailure(
        "validation failed after 3 attempts", attempts=3, last_error=None
    )

    with pytest.raises(LLMValidationFailure):
        enrich_vocab_item(item, mock_llm)
