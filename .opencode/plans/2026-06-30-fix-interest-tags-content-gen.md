# Plan — Activate interest-tag-driven personalized content generation

## Context

The nightly content generation pipeline has three celery tasks. Two run on schedule, one is dead code:

| Task | Beat schedule | Interest tags? | Generates for |
|------|--------------|----------------|---------------|
| `generate_shared_pool` (10 items) | 18:00 UTC | No — generic kid-friendly | All users |
| `run_daily` (enrichment) | 19:00 UTC | No — enriches existing empty-definition items | N/A |
| `generate_personalized` | **Never dispatched** | Yes — uses `user.interest_tags` | Single user (triggered by milestone) |

`generate_personalized` is fully implemented (prompt builder, exclusion list, persist+enroll, milestone idempotency, tests) but has zero dispatch paths: no beat schedule entry, no API endpoint calls it, no post-review hook. The interest tags feature exists in the database, validator, and prompt template but never activates automatically.

**Result:** users with interest tags set to `["animals", "family", "food"]` still see generic shared-pool vocab unrelated to those topics.

## Decision

Add a daily **per-user personalized generation tick**. A new celery task iterates all users and calls `generate_vocab_batch` with each user's `interest_tags`, persisting `count=5` items enrolled only to that user. Schedule it at 20:00 UTC (after shared pool and enrichment ticks complete, giving the LLM fresh exclusion context).

**Why not activate the existing `generate_personalized`?** It's milestone-triggered (`total_reviews % 30 == 0`) and gated on that. A daily per-user tick is the correct model for ongoing interest-driven content — users get fresh relevant vocabulary every night regardless of review milestones.

**Why not thread interests into `generate_shared_pool`?** The shared pool creates one batch enrolled to ALL users. Different users have different interests. A per-user approach is needed.

## Implementation

### 1. Extract shared helper from `_generate_personalized`

Refactor the core generation logic (LLM call + persist) out of `_generate_personalized` into a shared `_generate_personalized_batch()` async function:

```python
async def _generate_personalized_batch(
    session, user, count, llm
) -> dict[str, int | str]:
    # Build exclusion list (global + user tokens)
    # Call generate_vocab_batch(llm, interests=user.interest_tags)
    # Persist via _persist_batch_and_enroll (single user)
    # Return result dict
```

Then `_generate_personalized` calls this helper + milestone gate + updates `last_personalized_milestone`. The new task calls this helper without the milestone gate.

### 2. New celery task: `generate_personalized_for_all`

```python
@celery_app.task(name="content_gen.generate_personalized_for_all")
def generate_personalized_for_all(count: int = 5) -> dict[str, int | str]:
    return asyncio.run(_generate_personalized_for_all(count))


async def _generate_personalized_for_all(count: int) -> dict[str, int | str]:
    async with SessionLocal() as session:
        user_ids = list((await session.execute(select(User.id))).scalars().all())

    llm = LLMClient()
    total_created = 0
    for uid in user_ids:
        async with SessionLocal() as session:
            user = await session.get(User, uid)
            if user is None:
                continue

            # Same-day idempotency: skip if personalized vocab already created today
            start_of_day = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
            already = await session.execute(
                select(VocabItem.id).where(
                    VocabItem.source == "personalized",
                    VocabItem.created_at >= start_of_day,
                ).limit(1)
            ).scalar_one_or_none()
            if already is not None:
                continue

            result = await _generate_personalized_batch(session, user, count, llm)
            if "vocab_created" in result:
                total_created += result["vocab_created"]
            await session.commit()

    return {"total_vocab_created": total_created, "users_processed": len(user_ids)}
```

### 3. Add to beat schedule

**File:** `app/core/celery_app.py` — add to `beat_schedule`:

```python
"content-gen-personalized-all": {
    "task": "content_gen.generate_personalized_for_all",
    "schedule": crontab(hour=20, minute=0),
    "kwargs": {"count": 5},
},
```

### 4. Tests

**File:** `apps/api/tests/workers/test_content_gen.py`

- `test_generate_personalized_for_all_creates_vocab_for_each_user` — seed 2 users with different interest tags, run task, assert each gets new vocab with `source="personalized"`
- `test_generate_personalized_for_all_skips_on_same_day_idempotency` — pre-create personalized vocab for today, run task, assert user skipped
- `test_generate_personalized_for_all_handles_zero_users` — no users, returns `{"total_vocab_created": 0}`
- Existing `generate_personalized` tests must continue passing unchanged

### 5. Verification

1. `uv run pytest apps/api/tests/workers/test_content_gen.py` — new + existing tests pass
2. `pnpm test` + `pnpm lint` green
3. Manual: `celery call content_gen.generate_personalized_for_all --kwargs '{"count": 3}'` — verify vocab created
4. Check logs: `generate_personalized_for_all[<uuid>]: succeeded in 3s: {'total_vocab_created': 3, 'users_processed': 1}`

## Files

- `app/workers/content_gen.py` — extract helper, add new task
- `app/core/celery_app.py` — add beat schedule entry
- `apps/api/tests/workers/test_content_gen.py` — new tests

## Risks

- **LLM cost:** ~5 items/user/day. Single user → negligible. Scales linearly.
- **Same-day idempotency:** beat schedule double-fire is the main risk; the `created_at >= start_of_day` guard catches it.
- **Existing milestone gate preserved:** `generate_personalized` still triggers on milestones separately.
