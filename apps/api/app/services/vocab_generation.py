from __future__ import annotations

from app.schemas.llm import GeneratedVocabBatch
from app.services.llm import LLMClient

EXCLUDE_CAP = 500


def generate_vocab_batch(
    llm: LLMClient,
    *,
    language: str,
    count: int,
    exclude_tokens: list[str],
    interests: list[str] | None = None,
) -> GeneratedVocabBatch:
    # The exclusion list is a TOKEN-COST OPTIMIZATION only. We cap at the
    # 500 most-recent tokens because (a) newer words are statistically more
    # likely to be re-proposed by the LLM, and (b) sending the entire catalog
    # every call wastes input-token budget. The correctness gate against
    # duplicates is the unique constraint `uq_vocab_items_token_language`
    # at INSERT time in the caller.
    capped = exclude_tokens[:EXCLUDE_CAP]
    system_prompt = _build_system_prompt(language, capped, interests)
    user_prompt = _build_user_prompt(language, count, interests)
    return llm.complete(
        user_prompt,
        GeneratedVocabBatch,
        system_prompt=system_prompt,
        # ~150 tokens of content per item + JSON overhead + safety margin.
        # Tighter than a static 4000 — catches runaway completions earlier.
        max_tokens=count * 250 + 500,
    )


def _build_system_prompt(
    language: str, exclude_tokens: list[str], interests: list[str] | None
) -> str:
    lines = [
        "You are a vocabulary curator for an English learning app aimed at ESL "
        "learners aged 5-12 (Novakid-style audience). Generate kid-friendly, "
        "age-appropriate words.",
    ]
    if exclude_tokens:
        joined = ", ".join(exclude_tokens)
        lines.append(
            f"Do NOT propose any of these tokens, which already exist in the catalog: {joined}"
        )
    if interests:
        lines.append(f"Focus on these topics where appropriate: {', '.join(interests)}.")
    lines.append("Respond with valid JSON only, no commentary.")
    _ = language  # language is implied by the audience; reserved for future multi-language support
    return "\n\n".join(lines)


def _build_user_prompt(language: str, count: int, interests: list[str] | None) -> str:
    base = (
        f'Generate {count} new {language} vocabulary items as JSON with key "items" '
        "containing a list of objects each with fields: token, definition (20-500 chars), "
        "example (10-500 chars containing the token as a whole word)."
    )
    if interests:
        base += f" Tilt toward these topics: {', '.join(interests)}."
    return base
