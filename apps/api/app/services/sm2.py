from app.schemas.review import ReviewQuality, ReviewState, ReviewUpdate

EASE_FLOOR = 1.3


def compute_next_review(state: ReviewState, quality: ReviewQuality) -> ReviewUpdate:
    q = int(quality)
    delta = 0.1 - (5 - q) * (0.08 + (5 - q) * 0.02)
    return ReviewUpdate(
        ease_factor=max(EASE_FLOOR, state.ease_factor + delta),
        interval_days=1,
        repetitions=0,
    )
