from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from app.models.vocab_item import VocabItem
from app.schemas.llm import SimpleVocabExample
from app.services.llm import LLMClient, LLMValidationFailure

PROMPT_TEMPLATE = (
    "Define the {language} word '{token}' for an English-speaking ESL learner. "
    "Return JSON with these fields:\n"
    '  - "token": the word itself, exactly as given\n'
    '  - "definition": 1-2 sentence definition (20-500 chars)\n'
    '  - "example": one example sentence containing the word (10-500 chars)\n'
    "Return only the JSON object, no commentary."
)


def enrich_vocab_item(item: VocabItem, llm: LLMClient) -> SimpleVocabExample:
    """Call LLM to generate definition and example for item. Pure — no DB writes.
    LLMValidationFailure propagates to the caller."""
    prompt = PROMPT_TEMPLATE.format(language=item.language, token=item.token)
    return llm.complete(prompt, SimpleVocabExample)


@dataclass(frozen=True)
class EnrichmentOutcome:
    ready: bool
    llm_attempts: int  # LLM tries made on a validation failure; 0 on success


def apply_enrichment(item: VocabItem, llm: LLMClient, *, now: datetime) -> EnrichmentOutcome:
    """Run the Enrichment transition for one Vocab Item: pending -> ready.

    Mutates the item in place — on success sets `definition` + `example_sentence`
    and resets `enrichment_attempts`; on validation failure increments
    `enrichment_attempts` (ADR-0005). Either way stamps `last_enrichment_attempted_at`.
    The empty-`definition` sentinel (ADR-0001) flips to ready only on success. No DB
    commit — the caller owns the transaction; the returned outcome is for it to count/log.
    """
    item.last_enrichment_attempted_at = now
    try:
        result = enrich_vocab_item(item, llm)
    except LLMValidationFailure as exc:
        item.enrichment_attempts += 1
        return EnrichmentOutcome(ready=False, llm_attempts=exc.attempts)
    item.definition = result.definition
    item.example_sentence = result.example
    item.enrichment_attempts = 0
    return EnrichmentOutcome(ready=True, llm_attempts=0)
