import re
from pathlib import Path

_DENYLIST_FILE = Path(__file__).parent / "content_denylist.txt"


def _compile_pattern(terms: tuple[str, ...]) -> "re.Pattern[str] | None":
    if not terms:
        return None
    escaped = (re.escape(t) for t in terms)
    return re.compile(rf"\b(?:{'|'.join(escaped)})\b", flags=re.IGNORECASE)


_PATTERN: "re.Pattern[str] | None" = None


def load_denylist() -> None:
    global _PATTERN
    if not _DENYLIST_FILE.exists():
        _PATTERN = None
        return
    terms = tuple(
        line.strip()
        for line in _DENYLIST_FILE.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.strip().startswith("#")
    )
    _PATTERN = _compile_pattern(terms)


load_denylist()


def contains_disallowed_term(text: str) -> bool:
    if _PATTERN is None:
        return False
    return _PATTERN.search(text) is not None
