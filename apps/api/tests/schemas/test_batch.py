from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from pydantic import ValidationError


class TestDailyBatch:
    def test_happy_path_parses_valid_payload(self) -> None:
        from app.schemas.batch import Card, DailyBatch

        now = datetime.now(UTC)
        card = Card(
            review_id=uuid4(),
            vocab_item_id=uuid4(),
            token="hello",
            definition="a greeting",
            example_sentence="Hello, how are you?",
            ease_factor=2.5,
            interval_days=1,
            repetitions=5,
            due_at=now,
            word_audio_url=None,
            example_audio_url=None,
        )
        batch = DailyBatch(cards=[card])
        assert batch.cards[0].token == "hello"
        assert batch.cards[0].ease_factor == 2.5
        assert batch.cards[0].word_audio_url is None

    def test_empty_batch_is_valid(self) -> None:
        from app.schemas.batch import DailyBatch

        batch = DailyBatch(cards=[])
        assert batch.cards == []

    def test_ease_factor_must_be_at_least_1_3(self) -> None:
        from app.schemas.batch import Card

        now = datetime.now(UTC)
        with pytest.raises(ValidationError) as exc:
            Card(
                review_id=uuid4(),
                vocab_item_id=uuid4(),
                token="hello",
                definition="a greeting",
                example_sentence="Hello!",
                ease_factor=1.2,
                interval_days=1,
                repetitions=0,
                due_at=now,
            )
        assert "ease_factor" in str(exc.value)

    def test_interval_days_must_be_non_negative(self) -> None:
        from app.schemas.batch import Card

        now = datetime.now(UTC)
        with pytest.raises(ValidationError) as exc:
            Card(
                review_id=uuid4(),
                vocab_item_id=uuid4(),
                token="hello",
                definition="a greeting",
                example_sentence="Hello!",
                ease_factor=2.5,
                interval_days=-1,
                repetitions=0,
                due_at=now,
            )
        assert "interval_days" in str(exc.value)

    def test_repetitions_must_be_non_negative(self) -> None:
        from app.schemas.batch import Card

        now = datetime.now(UTC)
        with pytest.raises(ValidationError) as exc:
            Card(
                review_id=uuid4(),
                vocab_item_id=uuid4(),
                token="hello",
                definition="a greeting",
                example_sentence="Hello!",
                ease_factor=2.5,
                interval_days=1,
                repetitions=-1,
                due_at=now,
            )
        assert "repetitions" in str(exc.value)

    def test_example_sentence_is_optional(self) -> None:
        from app.schemas.batch import Card

        now = datetime.now(UTC)
        card = Card(
            review_id=uuid4(),
            vocab_item_id=uuid4(),
            token="hello",
            definition="a greeting",
            example_sentence=None,
            ease_factor=2.5,
            interval_days=1,
            repetitions=0,
            due_at=now,
        )
        assert card.example_sentence is None

    def test_audio_urls_are_optional_none_by_default(self) -> None:
        from app.schemas.batch import Card

        now = datetime.now(UTC)
        card = Card(
            review_id=uuid4(),
            vocab_item_id=uuid4(),
            token="hello",
            definition="a greeting",
            example_sentence="Hello!",
            ease_factor=2.5,
            interval_days=1,
            repetitions=0,
            due_at=now,
        )
        assert card.word_audio_url is None
        assert card.example_audio_url is None
