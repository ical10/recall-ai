import pytest
from pydantic import ValidationError

from app.schemas.review import ReviewQuality, ReviewState, ReviewUpdate


def test_review_state_accepts_valid_inputs() -> None:
    state = ReviewState(ease_factor=2.5, interval_days=0, repetitions=0)
    assert state.ease_factor == 2.5
    assert state.interval_days == 0
    assert state.repetitions == 0


def test_review_state_rejects_ease_below_floor() -> None:
    with pytest.raises(ValidationError):
        ReviewState(ease_factor=1.2, interval_days=0, repetitions=0)


def test_review_state_rejects_negative_interval() -> None:
    with pytest.raises(ValidationError):
        ReviewState(ease_factor=2.5, interval_days=-1, repetitions=0)


def test_review_state_rejects_negative_repetitions() -> None:
    with pytest.raises(ValidationError):
        ReviewState(ease_factor=2.5, interval_days=0, repetitions=-1)


def test_review_quality_enum_values() -> None:
    assert ReviewQuality.AGAIN == 0
    assert ReviewQuality.HARD == 2
    assert ReviewQuality.GOOD == 4
    assert ReviewQuality.EASY == 5


def test_review_update_accepts_valid_inputs() -> None:
    update = ReviewUpdate(ease_factor=2.5, interval_days=1, repetitions=1)
    assert update.ease_factor == 2.5
    assert update.interval_days == 1
    assert update.repetitions == 1


def test_review_update_rejects_ease_below_floor() -> None:
    with pytest.raises(ValidationError):
        ReviewUpdate(ease_factor=1.2, interval_days=1, repetitions=0)
