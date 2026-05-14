from app.models.vocab_item import VocabItem
from app.schemas.llm import SimpleVocabExample
from app.services.llm import LLMClient

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
