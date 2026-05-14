import re

_DISALLOWED_TERMS: tuple[str, ...] = (
    # Kept empty in the repo — populate locally from a gitignored file or env-driven
    # loader before going live. See ADR-0007.
)


def _compile_pattern(terms: tuple[str, ...]) -> "re.Pattern[str] | None":
    if not terms:
        return None
    escaped = (re.escape(t) for t in terms)
    return re.compile(rf"\b(?:{'|'.join(escaped)})\b", flags=re.IGNORECASE)


_PATTERN = _compile_pattern(_DISALLOWED_TERMS)


def contains_disallowed_term(text: str) -> bool:
    if _PATTERN is None:
        return False
    return _PATTERN.search(text) is not None
