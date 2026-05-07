from unittest.mock import MagicMock

import pytest

from app.models.vocab_item import VocabItem
from app.schemas.llm import SimpleVocabExample
from app.services.enrichment import enrich_vocab_item
from app.services.llm import LLMValidationFailure


def test_enrich_vocab_item_calls_llm_with_token_and_language() -> None:
    item = VocabItem(token="ephemeral", language="en", definition="", example_sentence=None)
    llm = MagicMock()
    llm.complete.return_value = SimpleVocabExample(
        token="ephemeral",
        definition="Lasting briefly; transient and short-lived.",
        example="The cherry blossoms were ephemeral but unforgettable.",
    )

    enrich_vocab_item(item, llm)

    llm.complete.assert_called_once()
    prompt = llm.complete.call_args.args[0]
    assert "ephemeral" in prompt
    assert "en" in prompt
    assert llm.complete.call_args.args[1] is SimpleVocabExample


def test_enrich_vocab_item_returns_validated_simple_vocab_example() -> None:
    item = VocabItem(token="ephemeral", language="en", definition="", example_sentence=None)
    expected = SimpleVocabExample(
        token="ephemeral",
        definition="Lasting briefly; transient and short-lived.",
        example="The cherry blossoms were ephemeral but unforgettable.",
    )
    llm = MagicMock()
    llm.complete.return_value = expected

    result = enrich_vocab_item(item, llm)

    assert result is expected


def test_enrich_vocab_item_propagates_llm_validation_failure() -> None:
    item = VocabItem(token="ephemeral", language="en", definition="", example_sentence=None)
    llm = MagicMock()
    llm.complete.side_effect = LLMValidationFailure(
        "validation failed after 3 attempts", attempts=3, last_error=None
    )

    with pytest.raises(LLMValidationFailure):
        enrich_vocab_item(item, llm)
