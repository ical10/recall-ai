import re

import pytest

from app.services.content_safety import contains_disallowed_term, load_denylist


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


def test_load_denylist_reads_baseline_file() -> None:
    import app.services.content_safety as cs_module

    load_denylist()

    assert cs_module.contains_disallowed_term("this is fucking great") is True
    assert cs_module.contains_disallowed_term("the cherry blossoms were beautiful") is False


def test_load_denylist_handles_missing_file(monkeypatch: pytest.MonkeyPatch) -> None:
    import pathlib

    import app.services.content_safety as cs_module

    monkeypatch.setattr(cs_module, "_DENYLIST_FILE", pathlib.Path("/does/not/exist.txt"))
    load_denylist()

    assert cs_module._PATTERN is None
    assert cs_module.contains_disallowed_term("anything fucking goes") is False


def test_load_denylist_ignores_comments_and_blank_lines(
    monkeypatch: pytest.MonkeyPatch, tmp_path: "object"
) -> None:
    import pathlib

    import app.services.content_safety as cs_module

    assert isinstance(tmp_path, pathlib.Path)
    fake = tmp_path / "denylist.txt"
    fake.write_text(
        "# This is a comment containing the word comment\n"
        "\n"
        "   # leading-space comment\n"
        "uniqueterm\n"
        "\n"
        "# trailing comment\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(cs_module, "_DENYLIST_FILE", fake)
    load_denylist()

    assert cs_module.contains_disallowed_term("the uniqueterm appears here") is True
    assert cs_module.contains_disallowed_term("this contains the word comment in it") is False
