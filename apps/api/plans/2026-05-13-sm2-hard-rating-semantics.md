# Slice 0.5 — Differentiate Hard from Again + dedupe `ReviewQuality`

**Goal:** Two related cleanups before Slice B opens the review UI:
1. Modify SM-2 so "Hard" (quality=2) is a small penalty on a passing review, not a full failure (matches Anki/RemNote/Mochi semantics). Prevents cards from being stuck at `repetitions=0, interval_days=1` whenever the user finds them slightly effortful. See [ADR-0006](../../../docs/adr/0006-hard-rating-as-anki-like-penalty.md).
2. Delete the duplicate `ReviewQuality` IntEnum in `app/schemas/review.py` and consolidate on `app/models/review.py`. The two enums are structurally identical but cause an `mypy --strict` failure as soon as anything imports from one and passes to a function annotated with the other (which Slice B does).

**Architecture:** Function change in `apps/api/app/services/sm2.py` plus a one-import-edit in `app/schemas/review.py` and `app/services/sm2.py`. No schema change. `ReviewState` and `ReviewUpdate` keep their existing fields.

**Tech stack:** Existing.

---

## File Structure

**Modify:**
- `apps/api/app/services/sm2.py` — branch `quality == HARD` separately from `quality < 3`; import `ReviewQuality` from `app.models.review`
- `apps/api/app/schemas/review.py` — delete the local `ReviewQuality` enum (keep `ReviewState` and `ReviewUpdate`); re-export `ReviewQuality` from `app.models.review` only if any test or sub-router currently imports it from `schemas` (grep first — if zero hits, just delete)
- `apps/api/tests/services/test_sm2.py` — add Hard-specific cases; adjust any existing test that asserted Hard = full failure; fix `ReviewQuality` import if it was pulled from `schemas`

**No edits to:** models (the surviving `ReviewQuality` definition stays where it is), migrations, routers, templates.

---

## Task 1: Dedupe `ReviewQuality`

- [ ] **Step 1**: Grep for imports of `ReviewQuality` from `app.schemas.review`:
```
rg "from app\.schemas\.review import .*ReviewQuality" apps/api
```
Update every hit to `from app.models.review import ReviewQuality`. Then delete the `ReviewQuality` class from `app/schemas/review.py` (lines 6-10 as of HEAD), leaving `ReviewState` and `ReviewUpdate` untouched.

- [ ] **Step 2**: Commit — `refactor: consolidate ReviewQuality on app.models.review`.

---

## Task 2: Branch Hard from Again in `compute_next_review`

- [ ] **Step 1**: Edit `apps/api/app/services/sm2.py`:

```python
from app.models.review import ReviewQuality
from app.schemas.review import ReviewState, ReviewUpdate

EASE_FLOOR = 1.3
QUALITY_PASS_THRESHOLD = 3
HARD_INTERVAL_MULTIPLIER = 1.2
HARD_EASE_PENALTY = 0.15


def compute_next_review(state: ReviewState, quality: ReviewQuality) -> ReviewUpdate:
    q = int(quality)

    # AGAIN (q=0): full failure — reset repetitions, push 1 day, ease drops via SM-2 delta.
    if q == ReviewQuality.AGAIN:
        delta = 0.1 - (5 - q) * (0.08 + (5 - q) * 0.02)
        new_ease = max(EASE_FLOOR, state.ease_factor + delta)
        return ReviewUpdate(ease_factor=new_ease, interval_days=1, repetitions=0)

    # HARD (q=2): pass with penalty — keep repetitions, reduce ease, mild interval growth.
    if q == ReviewQuality.HARD:
        new_ease = max(EASE_FLOOR, state.ease_factor - HARD_EASE_PENALTY)
        new_interval = max(1, round(state.interval_days * HARD_INTERVAL_MULTIPLIER))
        return ReviewUpdate(
            ease_factor=new_ease,
            interval_days=new_interval,
            repetitions=state.repetitions + 1,
        )

    # GOOD / EASY: canonical SM-2 progression.
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
```

- [ ] **Step 2**: Commit — `refactor: differentiate Hard (q=2) from Again (q=0) in compute_next_review`.

---

## Task 3: Tests

- [ ] **Step 1**: Read `apps/api/tests/services/test_sm2.py` and adjust any test that previously asserted `quality=2 → repetitions=0, interval_days=1`. The contract for q=2 is now:
  - `repetitions` becomes `state.repetitions + 1`
  - `interval_days` becomes `max(1, round(state.interval_days * 1.2))`
  - `ease_factor` drops by `HARD_EASE_PENALTY` (floored at `EASE_FLOOR`)

- [ ] **Step 2**: Add new cases:

```python
def test_hard_keeps_repetition_progression(...):
    # state(ease=2.5, interval=6, reps=2). compute_next_review(state, HARD).
    # assert reps=3, interval=round(6*1.2)=7, ease=2.35.

def test_hard_floors_ease_at_minimum(...):
    # state(ease=1.4, interval=10, reps=5). compute_next_review(state, HARD).
    # assert ease=1.3 (floored), interval=round(10*1.2)=12.

def test_hard_keeps_interval_at_least_one_day(...):
    # state(ease=2.5, interval=0, reps=0). compute_next_review(state, HARD).
    # assert interval=1 (not 0), reps=1.

def test_again_still_full_failure(...):
    # state(ease=2.5, interval=20, reps=4). compute_next_review(state, AGAIN).
    # assert reps=0, interval=1, ease dropped.

def test_good_and_easy_unchanged(...):
    # canonical SM-2 still applies — pick a regression case from the original test file.
```

- [ ] **Step 3**: Commit — `test: cover differentiated Hard semantics in compute_next_review`.

---

## Task 4: Verification + PR

- [ ] **Step 1**: Run targeted tests:
```
uv run pytest apps/api/tests/services/test_sm2.py -v
```

- [ ] **Step 2**: Lint:
```
pnpm lint
```

- [ ] **Step 3**: Open PR titled `refactor: dedupe ReviewQuality + differentiate Hard from Again`. Squash-merge before Slice B starts.

---

## Acceptance criteria

- A Review rated AGAIN (q=0) still resets repetitions to 0 and sets `interval_days=1`.
- A Review rated HARD (q=2) keeps progressing: `repetitions` increments, `interval_days = max(1, round(prev_interval * 1.2))`, `ease_factor` drops by `HARD_EASE_PENALTY` (floored at `EASE_FLOOR`).
- A Review rated GOOD (q=4) or EASY (q=5) behaves identically to before this change.
- All existing tests in `apps/api/tests/services/test_sm2.py` either pass unchanged (for Good/Easy/Again cases) or are updated for the new Hard contract; new Hard-specific tests pass.
- Exactly one `ReviewQuality` definition remains in the codebase (`apps/api/app/models/review.py`). `mypy --strict` passes against `apps/api/app`.

## Notes / gotchas

- **Forward-only behavior change.** Existing rows in production with `repetitions=0, interval_days=1` from prior Hard ratings will *not* be retroactively repaired — they just resume normal progression on the next Hard/Good/Easy rating.
- **Ease floor still applies.** `HARD_EASE_PENALTY = 0.15` is conservative; if you find cards "graduating too fast" after a Hard rating, the next dial to turn is `HARD_INTERVAL_MULTIPLIER` (toward 1.0 = "no growth on Hard").
- **Schemas untouched.** `ReviewQuality`, `ReviewState`, `ReviewUpdate` keep their existing fields and validators — Slice B's rating buttons don't change.
