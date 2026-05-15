import os
import re

_DISALLOWED_TERMS: tuple[str, ...] = ()


def _compile_pattern(terms: tuple[str, ...]) -> "re.Pattern[str] | None":
    if not terms:
        return None
    escaped = (re.escape(t) for t in terms)
    return re.compile(rf"\b(?:{'|'.join(escaped)})\b", flags=re.IGNORECASE)


_PATTERN: "re.Pattern[str] | None" = None


def load_denylist() -> None:
    global _PATTERN
    raw = os.environ.get("CONTENT_DENYLIST", "")
    if not raw:
        _PATTERN = None
        return
    terms = tuple(t.strip() for t in raw.split(",") if t.strip())
    _PATTERN = _compile_pattern(terms)


load_denylist()


def contains_disallowed_term(text: str) -> bool:
    if _PATTERN is None:
        return False
    return _PATTERN.search(text) is not None
