from app.models.review import ReviewQuality
from app.schemas.review import ReviewState, ReviewUpdate

EASE_FLOOR = 1.3
QUALITY_PASS_THRESHOLD = 3
HARD_INTERVAL_MULTIPLIER = 1.2
HARD_EASE_PENALTY = 0.15


def compute_next_review(state: ReviewState, quality: ReviewQuality) -> ReviewUpdate:
    if quality == ReviewQuality.AGAIN:
        delta = 0.1 - 5 * (0.08 + 5 * 0.02)
        new_ease = max(EASE_FLOOR, state.ease_factor + delta)
        return ReviewUpdate(ease_factor=new_ease, interval_days=1, repetitions=0)

    if quality == ReviewQuality.HARD:
        new_ease = max(EASE_FLOOR, state.ease_factor - HARD_EASE_PENALTY)
        new_interval = max(1, round(state.interval_days * HARD_INTERVAL_MULTIPLIER))
        return ReviewUpdate(
            ease_factor=new_ease,
            interval_days=new_interval,
            repetitions=state.repetitions + 1,
        )

    # GOOD / EASY: canonical SM-2 progression.
    q = int(quality)
    delta = 0.1 - (5 - q) * (0.08 + (5 - q) * 0.02)
    new_ease = max(EASE_FLOOR, state.ease_factor + delta)
    new_repetitions = state.repetitions + 1
    if new_repetitions == 1:
        new_interval = 1
    elif new_repetitions == 2:
        new_interval = 6
    else:
        new_interval = round(state.interval_days * new_ease)
    return ReviewUpdate(
        ease_factor=new_ease,
        interval_days=new_interval,
        repetitions=new_repetitions,
    )
