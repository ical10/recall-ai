from app.schemas.review import ReviewQuality, ReviewState, ReviewUpdate

EASE_FLOOR = 1.3
QUALITY_PASS_THRESHOLD = 3


def compute_next_review(state: ReviewState, quality: ReviewQuality) -> ReviewUpdate:
    q = int(quality)
    delta = 0.1 - (5 - q) * (0.08 + (5 - q) * 0.02)
    new_ease = max(EASE_FLOOR, state.ease_factor + delta)
    if q < QUALITY_PASS_THRESHOLD:
        return ReviewUpdate(ease_factor=new_ease, interval_days=1, repetitions=0)

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
