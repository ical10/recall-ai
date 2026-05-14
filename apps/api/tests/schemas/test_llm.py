import re

import pytest
from pydantic import ValidationError

from app.schemas.llm import SimpleVocabExample


def test_simple_vocab_example_passes_when_denylist_empty() -> None:
    obj = SimpleVocabExample(
        token="ephemeral",
        definition="Lasting briefly; transient and short-lived in nature.",
        example="The cherry blossoms were ephemeral but stunning.",
    )
    assert obj.token == "ephemeral"


def test_simple_vocab_example_rejects_disallowed_term_in_definition(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import app.services.content_safety as cs_module

    pattern = re.compile(r"\b(?:foo)\b", flags=re.IGNORECASE)
    monkeypatch.setattr(cs_module, "_PATTERN", pattern)

    with pytest.raises(ValidationError, match="disallowed term"):
        SimpleVocabExample(
            token="ephemeral",
            definition="A foo definition that meets the minimum length requirement here.",
            example="The cherry blossoms were ephemeral but stunning.",
        )


def test_simple_vocab_example_rejects_disallowed_term_in_example(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import app.services.content_safety as cs_module

    pattern = re.compile(r"\b(?:foo)\b", flags=re.IGNORECASE)
    monkeypatch.setattr(cs_module, "_PATTERN", pattern)

    with pytest.raises(ValidationError, match="disallowed term"):
        SimpleVocabExample(
            token="ephemeral",
            definition="Lasting briefly; transient and short-lived in nature.",
            example="The foo blossoms were ephemeral but stunning.",
        )
