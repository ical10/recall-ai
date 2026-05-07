from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.schemas.vocab import VocabCreate, VocabListResponse, VocabRead


def test_vocab_create_valid() -> None:
    vocab = VocabCreate(token="hello", language="en")
    assert vocab.token == "hello"
    assert vocab.language == "en"


def test_vocab_create_token_required() -> None:
    with pytest.raises(ValidationError):
        VocabCreate(token="", language="en")


def test_vocab_create_token_max_length() -> None:
    long_token = "a" * 256
    with pytest.raises(ValidationError):
        VocabCreate(token=long_token, language="en")


def test_vocab_create_language_min_length() -> None:
    with pytest.raises(ValidationError):
        VocabCreate(token="hello", language="e")


def test_vocab_create_language_max_length() -> None:
    long_language = "a" * 36
    with pytest.raises(ValidationError):
        VocabCreate(token="hello", language=long_language)


def test_vocab_read_valid() -> None:
    vocab_id = uuid4()
    vocab = VocabRead(
        id=vocab_id,
        token="hello",
        language="en",
        part_of_speech="noun",
        definition="a greeting",
        example_sentence="Hello, world!",
    )
    assert vocab.id == vocab_id
    assert vocab.token == "hello"
    assert vocab.language == "en"
    assert vocab.part_of_speech == "noun"
    assert vocab.definition == "a greeting"
    assert vocab.example_sentence == "Hello, world!"


def test_vocab_list_response_valid() -> None:
    vocab_id = uuid4()
    items = [
        VocabRead(
            id=vocab_id,
            token="hello",
            language="en",
            definition="a greeting",
        )
    ]
    response = VocabListResponse(items=items, page=1, page_size=10, total=1)
    assert len(response.items) == 1
    assert response.items[0].token == "hello"
    assert response.page == 1
    assert response.page_size == 10
    assert response.total == 1
