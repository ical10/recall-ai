# RecallAI

Spaced-repetition vocabulary trainer with LLM-generated content for ESL learners.

## Language

**Vocab Item**:
A word or phrase a learner is studying, with its language, definition, and example.
_Avoid_: word (ambiguous), card (per-user concept)

**Review**:
A user's relationship to a Vocab Item — the SM-2 state (ease, interval, repetitions), due date, and suspension flag.
_Avoid_: card (in code), schedule

**Enrichment**:
The pipeline step that fills a Vocab Item's `definition` and `example_sentence` from the LLM. Runs nightly via Celery beat against pending items.

**Enrichment Status**:
A binary state encoded directly on the Vocab Item: `definition == ""` means **pending**, non-empty means **ready**. There is no enum or status column — the empty string is the sentinel. See [ADR-0001](./docs/adr/0001-empty-string-sentinel-for-enrichment-state.md).

**Due**:
A Review whose `due_at` is null or in the past. Null `due_at` means "never reviewed" and is treated as immediately due.

**Suspended**:
A per-user flag on a Review that excludes it from the review queue without deleting it.

**User Timezone**:
Each User has a `timezone` (IANA name, default `"UTC"`). All user-facing date bucketing — streak day boundaries, "due today" cutoff — is evaluated in this timezone. The nightly content-gen cron is global and stays UTC-anchored. See [ADR-0004](./docs/adr/0004-per-user-timezone-on-user-model.md).

**Quality Rating**:
The user's self-assessed recall difficulty for a Review, expressed on the SM-2 scale: Again (0), Hard (2), Good (4), Easy (5). Again resets repetitions; Hard counts as a pass with a small ease/interval penalty; Good and Easy progress normally. See [ADR-0006](./docs/adr/0006-hard-rating-as-anki-like-penalty.md).

**Again Re-queue**:
An in-session retry mechanism layered on top of SM-2. When the user rates a card "Again" (quality=0), the row still gets the canonical SM-2 1-day push, but the card is also held in a short-lived per-session list and resurfaced ~10 minutes later in the same browser session. Persisted in a signed session cookie. See [ADR-0002](./docs/adr/0002-session-cookie-again-requeue.md).

## Relationships

- A **Vocab Item** is shared across users; a **Review** is per-user (unique on `(user_id, vocab_item_id)`)
- A **Vocab Item** progresses through one **Enrichment**: pending → ready
- A **Review** appears in `/review` only when its Vocab Item is **ready** AND the Review is **due** AND not **suspended**
- A **Quality Rating** drives the SM-2 update that sets the next `due_at` and `interval_days` on a Review

## Example dialogue

> **Dev:** When the seed script creates a new **Vocab Item** with empty definition, does the user see it in `/review` immediately?
> **Domain expert:** No — `/review` skips items that are still **pending**. They appear after the next nightly **Enrichment** flips them to **ready**.

> **Dev:** Why is a "card" sometimes the Vocab Item and sometimes the Review?
> **Domain expert:** It shouldn't be either. In code we call them by their proper names. "Card" only survives as informal speech.

## Flagged ambiguities

- "card" was used informally for both **Vocab Item** and **Review** — resolved: Vocab Item is the dictionary entry (shared), Review is the per-user study state.
