from unittest.mock import MagicMock

from app.schemas.llm import GeneratedVocabBatch, SimpleVocabExample
from app.services.vocab_generation import generate_vocab_batch


def _canned_batch() -> GeneratedVocabBatch:
    return GeneratedVocabBatch(
        items=[
            SimpleVocabExample(
                token="ephemeral",
                definition="Lasting briefly; transient and short-lived.",
                example="The cherry blossoms were ephemeral but unforgettable.",
            )
        ]
    )


def test_generate_vocab_batch_calls_llm_with_generated_vocab_batch_schema() -> None:
    llm = MagicMock()
    llm.complete.return_value = _canned_batch()

    result = generate_vocab_batch(llm, language="en", count=1, exclude_tokens=[])

    assert isinstance(result, GeneratedVocabBatch)
    schema_passed = llm.complete.call_args.args[1]
    assert schema_passed is GeneratedVocabBatch


def test_generate_vocab_batch_caps_exclude_tokens_in_system_prompt() -> None:
    llm = MagicMock()
    llm.complete.return_value = _canned_batch()
    many = [f"word{i}" for i in range(600)]

    generate_vocab_batch(llm, language="en", count=1, exclude_tokens=many)

    system_prompt = llm.complete.call_args.kwargs["system_prompt"]
    assert "word0" in system_prompt
    assert "word499" in system_prompt
    assert "word500" not in system_prompt
    assert "word599" not in system_prompt


def test_generate_vocab_batch_computes_max_tokens_from_count() -> None:
    llm = MagicMock()
    llm.complete.return_value = _canned_batch()

    generate_vocab_batch(llm, language="en", count=10, exclude_tokens=[])

    assert llm.complete.call_args.kwargs["max_tokens"] == 10 * 250 + 500


def test_generate_vocab_batch_includes_interests_when_provided() -> None:
    llm = MagicMock()
    llm.complete.return_value = _canned_batch()

    generate_vocab_batch(
        llm, language="en", count=1, exclude_tokens=[], interests=["animals", "food"]
    )

    system_prompt = llm.complete.call_args.kwargs["system_prompt"]
    assert "animals" in system_prompt
    assert "food" in system_prompt
    user_prompt = llm.complete.call_args.args[0]
    assert "animals" in user_prompt or "food" in user_prompt


def test_generate_vocab_batch_omits_interests_block_when_none() -> None:
    llm = MagicMock()
    llm.complete.return_value = _canned_batch()

    generate_vocab_batch(llm, language="en", count=1, exclude_tokens=[])

    system_prompt = llm.complete.call_args.kwargs["system_prompt"]
    assert "Focus on these topics" not in system_prompt


def test_generate_vocab_batch_system_prompt_anchors_kid_audience() -> None:
    llm = MagicMock()
    llm.complete.return_value = _canned_batch()

    generate_vocab_batch(llm, language="en", count=1, exclude_tokens=[])

    system_prompt = llm.complete.call_args.kwargs["system_prompt"]
    assert "5-12" in system_prompt or "5–12" in system_prompt
    assert "kid-friendly" in system_prompt
