# SM-2 Spaced Repetition Algorithm Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement the SM-2 spaced repetition algorithm as a pure function with strict pydantic input/output schemas and exhaustive table-driven tests. Zero coupling to DB, HTTP, or LLM — this is the math layer the review flow will call.

**Architecture:** A single function `compute_next_review(state: ReviewState, quality: ReviewQuality) -> ReviewUpdate` in `app/services/sm2.py`. Input/output are pydantic models. The function is total: every `(state, quality)` pair returns a valid `ReviewUpdate`. Quality below `GOOD` (3) resets the card; quality at or above `GOOD` advances. Ease factor floors at 1.3 per the standard SM-2 paper.

**Tech Stack:** Python 3.11, pydantic v2.

---

## File Structure

**Create:**
- `apps/api/app/schemas/review.py` — `ReviewState` (input) and `ReviewUpdate` (output) pydantic models, plus `ReviewQuality` int enum (re-imported from `app.models.review` if that lands first; if not, defined here)
- `apps/api/app/services/sm2.py` — pure function `compute_next_review`
- `apps/api/tests/services/__init__.py` — package marker
- `apps/api/tests/services/test_sm2.py` — table-driven tests covering the full transition matrix + edge cases

**Modify:**
- `apps/api/app/schemas/__init__.py` — re-export `ReviewState`, `ReviewUpdate`, `ReviewQuality`

**No edits to:** anything else.

---

## Background: SM-2 transitions

For each review, given current `(ease_factor: float, interval_days: int, repetitions: int)` and a recall `quality: int (0-5)`:

1. **If `quality < 3` (failure)** — reset:
   - `repetitions = 0`
   - `interval_days = 1`
   - `ease_factor` decreases (clamped at 1.3): `ease_factor = max(1.3, ease_factor + (0.1 - (5 - quality) * (0.08 + (5 - quality) * 0.02)))`
2. **If `quality >= 3` (success)** — advance:
   - `repetitions += 1`
   - First success: `interval_days = 1`
   - Second success: `interval_days = 6`
   - `ease_factor` is updated first per the formula above (the implementation clamps at 1.3 unconditionally; in this project's enum the success branch only ever sees q∈{GOOD=4, EASY=5} where delta≥0, but standard SM-2 q=3 produces a negative delta so the floor still matters in principle)
   - Subsequent: `interval_days = round(previous_interval_days * new_ease_factor)` — canonical SM-2 multiplies by the *post-update* ease (Wozniak), not the pre-update ease (Anki's variant)

The `due_at` is `now + timedelta(days=interval_days)` — but `compute_next_review` returns the updates as data; the caller decides when to apply `now`.

Quality enum values used in this project: `AGAIN=0`, `HARD=2`, `GOOD=4`, `EASY=5` (matching `ReviewQuality` in `app.models.review` if that's already landed).

---

## Task 1: Schemas (TDD)

- [ ] **Step 1**: Create `apps/api/tests/services/__init__.py` (empty).

- [ ] **Step 2**: Create `apps/api/tests/services/test_sm2.py` with the schema tests first:

```python
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
```

- [ ] **Step 3**: Run; fail with `ModuleNotFoundError`.

- [ ] **Step 4**: Implement `apps/api/app/schemas/review.py`:

```python
import enum

from pydantic import BaseModel, Field


class ReviewQuality(enum.IntEnum):
    AGAIN = 0
    HARD = 2
    GOOD = 4
    EASY = 5


class ReviewState(BaseModel):
    ease_factor: float = Field(ge=1.3)
    interval_days: int = Field(ge=0)
    repetitions: int = Field(ge=0)


class ReviewUpdate(BaseModel):
    ease_factor: float = Field(ge=1.3)
    interval_days: int = Field(ge=0)
    repetitions: int = Field(ge=0)
```

If `app.models.review` already exports a `ReviewQuality`, import it from there instead of redefining (check for the file first; if it exists with the same enum values, do `from app.models.review import ReviewQuality` and re-export).

- [ ] **Step 5**: Run; pass.

- [ ] **Step 6**: Update `apps/api/app/schemas/__init__.py`:

```python
from app.schemas.review import ReviewQuality, ReviewState, ReviewUpdate

__all__ = ["ReviewQuality", "ReviewState", "ReviewUpdate"]
```

- [ ] **Step 7**: Commit — `feat: add ReviewState/ReviewUpdate/ReviewQuality schemas for SM-2`.

---

## Task 2: SM-2 algorithm — failure path (TDD)

- [ ] **Step 1**: Append failure-path tests to `test_sm2.py`:

```python
from app.services.sm2 import compute_next_review


def test_failure_resets_repetitions_and_interval_to_1() -> None:
    state = ReviewState(ease_factor=2.5, interval_days=20, repetitions=5)
    update = compute_next_review(state, ReviewQuality.AGAIN)
    assert update.repetitions == 0
    assert update.interval_days == 1


def test_failure_decreases_ease_factor() -> None:
    state = ReviewState(ease_factor=2.5, interval_days=20, repetitions=5)
    update = compute_next_review(state, ReviewQuality.AGAIN)
    # AGAIN (q=0): delta = 0.1 - 5*(0.08 + 5*0.02) = 0.1 - 5*0.18 = -0.8
    assert update.ease_factor == pytest.approx(1.7, abs=1e-9)


def test_failure_clamps_ease_factor_at_floor() -> None:
    state = ReviewState(ease_factor=1.4, interval_days=20, repetitions=5)
    update = compute_next_review(state, ReviewQuality.AGAIN)
    assert update.ease_factor == pytest.approx(1.3, abs=1e-9)


def test_hard_quality_treated_as_failure() -> None:
    state = ReviewState(ease_factor=2.5, interval_days=20, repetitions=5)
    update = compute_next_review(state, ReviewQuality.HARD)
    assert update.repetitions == 0
    assert update.interval_days == 1
```

- [ ] **Step 2**: Run; fail with `ModuleNotFoundError: app.services.sm2`.

- [ ] **Step 3**: Implement `apps/api/app/services/sm2.py`:

```python
from app.schemas.review import ReviewQuality, ReviewState, ReviewUpdate

EASE_FLOOR = 1.3
QUALITY_PASS_THRESHOLD = 3


def _new_ease(ease: float, quality: int) -> float:
    delta = 0.1 - (5 - quality) * (0.08 + (5 - quality) * 0.02)
    return max(EASE_FLOOR, ease + delta)


def compute_next_review(state: ReviewState, quality: ReviewQuality) -> ReviewUpdate:
    q = int(quality)
    if q < QUALITY_PASS_THRESHOLD:
        return ReviewUpdate(
            ease_factor=_new_ease(state.ease_factor, q),
            interval_days=1,
            repetitions=0,
        )
    raise NotImplementedError("success path lands in next task")
```

- [ ] **Step 4**: Run failure-path tests; pass. Success-path tests (added in next task) will fail temporarily, which is expected.

- [ ] **Step 5**: Commit — `feat: add SM-2 failure-path computation`.

---

## Task 3: SM-2 algorithm — success path (TDD)

- [ ] **Step 1**: Append success-path tests:

```python
def test_first_success_sets_interval_to_1() -> None:
    state = ReviewState(ease_factor=2.5, interval_days=0, repetitions=0)
    update = compute_next_review(state, ReviewQuality.GOOD)
    assert update.repetitions == 1
    assert update.interval_days == 1


def test_second_success_sets_interval_to_6() -> None:
    state = ReviewState(ease_factor=2.5, interval_days=1, repetitions=1)
    update = compute_next_review(state, ReviewQuality.GOOD)
    assert update.repetitions == 2
    assert update.interval_days == 6


def test_third_success_multiplies_by_ease_factor() -> None:
    state = ReviewState(ease_factor=2.5, interval_days=6, repetitions=2)
    update = compute_next_review(state, ReviewQuality.GOOD)
    assert update.repetitions == 3
    assert update.interval_days == 15  # round(6 * 2.5) = 15


def test_subsequent_success_continues_to_multiply() -> None:
    state = ReviewState(ease_factor=2.6, interval_days=15, repetitions=3)
    update = compute_next_review(state, ReviewQuality.EASY)
    assert update.repetitions == 4
    # EASY (q=5): delta=0.1, new_ease=2.7; round(15 * 2.7) = round(40.5) = 40 (banker's)
    assert update.interval_days == 40


def test_good_quality_increases_ease_factor() -> None:
    state = ReviewState(ease_factor=2.5, interval_days=0, repetitions=0)
    update = compute_next_review(state, ReviewQuality.GOOD)
    # GOOD (q=4): delta = 0.1 - 1*(0.08 + 1*0.02) = 0.1 - 0.10 = 0
    assert update.ease_factor == pytest.approx(2.5, abs=1e-9)


def test_easy_quality_increases_ease_factor_more() -> None:
    state = ReviewState(ease_factor=2.5, interval_days=0, repetitions=0)
    update = compute_next_review(state, ReviewQuality.EASY)
    # EASY (q=5): delta = 0.1 - 0*(0.08 + 0) = 0.1
    assert update.ease_factor == pytest.approx(2.6, abs=1e-9)


@pytest.mark.parametrize(
    "quality,expected_delta",
    [
        (ReviewQuality.GOOD, 0.0),  # q=4
        (ReviewQuality.EASY, 0.1),  # q=5
    ],
)
def test_ease_factor_deltas(quality: ReviewQuality, expected_delta: float) -> None:
    state = ReviewState(ease_factor=2.5, interval_days=0, repetitions=0)
    update = compute_next_review(state, quality)
    assert update.ease_factor == pytest.approx(2.5 + expected_delta, abs=1e-9)
```

- [ ] **Step 2**: Run; success-path tests fail with `NotImplementedError`.

- [ ] **Step 3**: Replace the `compute_next_review` body in `apps/api/app/services/sm2.py`:

```python
def compute_next_review(state: ReviewState, quality: ReviewQuality) -> ReviewUpdate:
    q = int(quality)
    new_ease = _new_ease(state.ease_factor, q)
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
```

- [ ] **Step 4**: Run; all 12+ tests pass.

- [ ] **Step 5**: Commit — `feat: add SM-2 success-path computation with ease-factor adjustment`.

---

## Task 4: Determinism + property test

- [ ] **Step 1**: Append:

```python
def test_compute_is_deterministic() -> None:
    state = ReviewState(ease_factor=2.5, interval_days=10, repetitions=3)
    a = compute_next_review(state, ReviewQuality.GOOD)
    b = compute_next_review(state, ReviewQuality.GOOD)
    assert a == b


def test_compute_does_not_mutate_input() -> None:
    state = ReviewState(ease_factor=2.5, interval_days=10, repetitions=3)
    snapshot = state.model_copy()
    compute_next_review(state, ReviewQuality.AGAIN)
    assert state == snapshot
```

- [ ] **Step 2**: Run; must pass without changes (pydantic models are immutable by default in v2 frozen mode... actually they are mutable by default — but the function builds a new `ReviewUpdate` instead of mutating, so the input stays intact).

- [ ] **Step 3**: Commit — `test: assert SM-2 determinism and input immutability`.

---

## Out of Scope

- `due_at` calculation (`now + interval_days`) — that's a route-handler concern, not algorithm
- DB persistence of review state
- FSRS algorithm (CLAUDE.md flags as a future upgrade)
- Lapses-tracking / leech detection
- Anything multi-card (deck management, daily limits)

## Risks

- **Pydantic field constraint `ease_factor: Field(ge=1.3)`** — `ReviewState` rejects ease below 1.3. Since the algorithm clamps at 1.3 on update and initial state defaults to 2.5, this is safe. But if we ever ingest historical data with a lower ease, the schema will reject — caller must clamp before constructing `ReviewState`.
- **`round()` is banker's rounding in Python 3** — `round(2.5) == 2`, not 3. The SM-2 paper isn't precise about rounding direction. Standard practice is "round half up" via `math.floor(x + 0.5)`. Acceptable for now; revisit if user-visible interval feels off.
