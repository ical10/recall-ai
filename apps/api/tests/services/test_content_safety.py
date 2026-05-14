import re

import pytest

from app.services.content_safety import contains_disallowed_term


def test_contains_disallowed_term_returns_false_for_clean_text() -> None:
    assert contains_disallowed_term("The cherry blossoms were beautiful.") is False


def test_contains_disallowed_term_returns_false_when_denylist_empty() -> None:
    assert contains_disallowed_term("") is False


def test_contains_disallowed_term_is_case_insensitive(monkeypatch: pytest.MonkeyPatch) -> None:
    import app.services.content_safety as cs_module

    pattern = re.compile(r"\b(?:foo)\b", flags=re.IGNORECASE)
    monkeypatch.setattr(cs_module, "_PATTERN", pattern)

    assert cs_module.contains_disallowed_term("FOO bar") is True
    assert cs_module.contains_disallowed_term("foo bar") is True
    assert cs_module.contains_disallowed_term("Foo bar") is True


def test_contains_disallowed_term_uses_word_boundaries(monkeypatch: pytest.MonkeyPatch) -> None:
    import app.services.content_safety as cs_module

    pattern = re.compile(r"\b(?:ass)\b", flags=re.IGNORECASE)
    monkeypatch.setattr(cs_module, "_PATTERN", pattern)

    assert cs_module.contains_disallowed_term("asset management") is False
    assert cs_module.contains_disallowed_term("class assignment") is False
    assert cs_module.contains_disallowed_term("ass") is True
