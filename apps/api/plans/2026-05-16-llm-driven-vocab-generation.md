# PRD — LLM-driven vocab generation (shared pool + personalized milestones)

## Problem Statement

Vocabulary only enters the catalog when a user types it into the dashboard
form. The LLM enriches what users submit but never proposes anything new.
For ESL kids on a Novakid-style platform (ages 5–12) this is a dead end:
they don't know what they don't know, and asking a 7-year-old to type
"ephemeral" is not the value prop. The deck doesn't grow on its own; users
who run out of cards to review have nothing to come back to.

Two related satisfaction gaps compound the content problem:

1. **Engaged users get no acknowledgement of their investment.** A user who
   has rated 30 cards and a user who has rated 3 see the same dashboard.
2. **The platform has no signal for catalog provenance**, so we can't tell
   whether the catalog is growing because users are typing words in or
   because of system-generated content; can't analyze which sources retain
   better; can't safely run cost experiments.

## Solution

Two complementary LLM-driven generation services, both reusing the existing
enrichment pipeline (Pydantic validation, content-safety denylist,
retry-with-refinement loop, structured token-cost logging):

1. **Shared pool** — a daily Celery Beat task generates ~10 new
   kid-friendly English vocabulary items and auto-enrolls every user in
   reviews for them. Cheap, broad, keeps everyone moving.
2. **Personalized milestone drops** — a Celery task triggered from the
   review-rate endpoint at multiples of 30 completed reviews. Generates
   ~5 vocabulary items steered by the user's selected interest tags.
   Rewards engagement, deepens specialization, runs rarely so cost stays
   trivial.

Backed by:

- A `SYSTEM_PROMPT` extension to `LLMClient.complete()` that includes a
  capped (500 most-recent) exclusion list of existing tokens, preventing
  the LLM from proposing duplicates and burning input tokens. The
  database `uq_vocab_items_token_language` unique constraint remains the
  correctness gate; the cap is purely a cost optimization.
- A `/settings` page where the user picks from a curated set of 14
  kid-friendly tag categories (animals, food, school, etc.). Defaults to
  `["animals", "family", "food"]` so the feature works from day one
  without explicit configuration.
- A dashboard "you earned this" banner that appears the next time the
  user lands on `/dashboard` after a milestone fires, giving kids the
  visible feedback loop the satisfaction goal requires.
- A `source` provenance column on vocab items (`user`, `starter`,
  `shared_pool`, `personalized`) used for shared-pool same-day
  idempotency AND for future analytics.
- A `last_personalized_milestone` marker on users that prevents Celery
  retries from double-charging the LLM for the same milestone.

## User Stories

1. As an ESL kid learner, I want new vocabulary to appear in my deck
   automatically each day, so that I never run out of cards to review and
   can keep my streak going.
2. As an ESL kid learner, I want the new vocabulary to be age-appropriate
   (animals, family, school, food, colors, etc.), so that I can actually
   understand and use the words I'm learning.
3. As an engaged learner (parent or self-directed kid), I want a visible
   reward when I hit milestones like 30 reviews, so that my effort feels
   recognized and I'm motivated to continue.
4. As an engaged learner, I want my personalized vocabulary drops to
   reflect topics I actually care about, so that the words I'm learning
   feel relevant to my world.
5. As a learner (or parent on their behalf), I want to choose from a
   curated set of topic categories on a Settings page, so that I'm not
   asked to type free-form interests in a language I'm still learning.
6. As a learner who has chosen interest tags, I want my next milestone
   drop to be steered by those tags, so that picking topics actually
   changes what I get.
7. As a learner who has NOT yet chosen interest tags, I want sensible
   defaults to be applied automatically, so that the feature works for me
   without any setup.
8. As a learner, I want my milestone reward banner to persist on the
   dashboard until I open the new words, so that I don't miss the
   announcement if I close the browser.
9. As a learner who has already opened my milestone words, I want the
   banner to disappear, so that the next milestone's banner is meaningful
   when it appears.
10. As a returning user who was on the platform before this feature
    shipped, I want my account to receive the same default interest tags
    as new users, so that the personalization feature works for me
    immediately after the deploy.
11. As a developer running the solo project, I want a `source` column on
    every vocab item, so that I can grep the catalog by origin and
    measure how much auto-generated content vs user content my system has.
12. As a developer who pays per LLM call, I want the system to never
    re-generate vocab the catalog already has, so that I don't burn input
    tokens listing every existing word in every prompt.
13. As a developer, I want the shared-pool task to skip silently if it
    already ran today, so that a misconfigured second beat process or a
    manual `celery call` doesn't double-charge me.
14. As a developer, I want the personalized task to be idempotent per
    milestone, so that a Celery retry after a transient DB blip doesn't
    cost me a second LLM batch for the same user's same milestone.
15. As a developer, I want validation-exhaustion failures in the LLM to
    NOT trigger Celery's task-level retries, so that one broken prompt
    can't cascade into nine LLM calls (3 task retries × 3 in-loop
    refinement retries).
16. As a developer, I want transient infra failures (network, DB) to
    still trigger Celery retries, so that I don't lose work to a 5-second
    Postgres hiccup.
17. As a developer, I want `LLMClient.complete()` to accept an optional
    `system_prompt` parameter, so that any future feature needing system
    messages can extend the existing client without duplicating the
    OpenAI SDK boilerplate.
18. As a developer, I want `LLMClient.complete()` to accept a per-call
    `max_tokens` override, so that batch-generation calls can request the
    higher cap they need without forcing single-item enrichment to
    over-allocate.
19. As a developer, I want the `max_tokens` for batch generation to scale
    with batch size, so that tighter caps catch runaway completions
    earlier (cost protection) without truncating valid output.
20. As a developer, I want every state-changing settings POST to be
    protected against CSRF, so that an attacker can't overwrite a logged-in
    user's interest tags via a malicious third-party page.
21. As a developer, I want the SYSTEM_PROMPT exclusion list to be capped
    at 500 most-recent tokens, so that input-token cost stays bounded as
    the catalog grows.
22. As a developer, I want the database unique constraint on
    `(token, language)` to act as the final dedupe safety net, so that
    even if the LLM proposes a word outside the recent-500 window, the
    catalog stays clean.
23. As a developer, I want the Celery worker to log structured
    `extra={"task": ..., "user_id": ..., "attempts": ...}` records on
    every generation event, so that I can debug cost anomalies and
    catalog drift after the fact.
24. As a developer, I want the migration that adds the new columns to
    backfill existing users with the default interest tags and existing
    vocab items with `source='user'` (or `'starter'` for the 12 known
    seed tokens), so that no application code has to handle nullable
    legacy state.
25. As a developer, I want the migration to be reversible
    (down-migration drops the new columns cleanly), so that I can roll
    back the deploy without losing the database.
26. As a developer, I want the milestone-trigger logic in the rate
    endpoint to swallow Celery enqueue failures, so that a Redis outage
    can't 500 the user's review session.
27. As an operator, I want existing Railway worker + beat services to
    pick up the new task definitions automatically on the next deploy,
    so that no manual infrastructure change is needed.
28. As an operator, I want the worker container to remain free of the
    Tailwind/Node build (per the existing nixpacks worker config), so
    that worker deploys stay fast.

## Implementation Decisions

### Modules to build

**Deep modules (encapsulate logic, testable in isolation):**

- **`vocab_generation` service** — single public function
  `generate_vocab_batch(llm, *, language, count, exclude_tokens,
  interests) -> GeneratedVocabBatch`. Hides: SYSTEM_PROMPT construction,
  exclusion-list capping at 500, computed `max_tokens` (`count * 250 +
  500`), interest-steering prompt shape. Pure function with one I/O
  dependency (the LLM client).

- **`interests` service** — `TOPIC_TAGS` tuple (14 kid-friendly
  categories: `animals, colors, family, food, school, toys_and_games,
  weather, sports, body, clothing, nature, feelings, transportation,
  holidays`) + `is_valid_tag(tag: str) -> bool`. Single source of truth
  for the allowed tag taxonomy. Code-side, not DB-side, so the taxonomy
  is auditable in git history.

- **Extended `LLMClient.complete()`** — new keyword-only parameters:
  `system_prompt: str | None = None` (prepended as `{"role": "system",
  ...}` at index 0, persists across the refinement-retry loop) and
  `max_tokens: int | None = None` (per-call override of
  `self._max_tokens`). Backwards-compatible — every existing call site
  works unchanged.

**Shallow orchestration modules (thin glue, integration-tested):**

- **Two new Celery tasks** in the existing `content_gen` worker module.
  - `content_gen.generate_shared_pool(count=10)` — beat-scheduled at
    18:00 UTC daily. Same-day idempotency via
    `SELECT 1 FROM vocab_items WHERE source='shared_pool' AND
    created_at >= date_trunc('day', now()) LIMIT 1`. Mass-enrolls every
    user via the existing `_seed_starter_vocab`-style idempotent loop.
  - `content_gen.generate_personalized(user_id, count=5)` —
    rate-endpoint-triggered (not beat). Milestone idempotency via
    `last_personalized_milestone >= current_milestone` check at task
    start.

- **Milestone trigger** added to the existing `/review/{id}/rate`
  endpoint. After the rate commit, count `Review.last_reviewed_at IS NOT
  NULL` for the user; if `total > 0 and total % 30 == 0`, enqueue
  `content_gen.generate_personalized`. Wrap `send_task` in `try/except
  Exception` so a Redis outage doesn't 500 the rate endpoint.

- **Settings router** with two endpoints:
  - `GET /settings` — renders settings page with current tags pre-checked.
  - `POST /settings/interests` — validates submitted tags against
    `TOPIC_TAGS`, persists to `user.interest_tags`, returns HTMX partial.

- **Milestone-seen route**: `POST /milestones/seen` — sets
  `user.last_milestone_seen = user.last_personalized_milestone`. Returns
  HTMX redirect to `/review`.

- **Stats extension**: `compute_user_stats` populates a new
  `unseen_milestone: int | None` field (`last_personalized_milestone` if
  it exceeds `last_milestone_seen`, else None). Dashboard template uses
  this to conditionally render the banner.

### Schema changes (migration 0004)

Single migration `0004_add_vocab_generation_fields.py`:

1. `users.interest_tags JSON NOT NULL DEFAULT '["animals","family","food"]'`
   — JSON (not JSONB) for SQLite test compatibility. Model also sets
   `default=lambda: ["animals", "family", "food"]` so Python-side
   instantiation gets the same default.
2. `users.last_personalized_milestone INTEGER NOT NULL DEFAULT 0`
3. `users.last_milestone_seen INTEGER NOT NULL DEFAULT 0`
4. `vocab_items.source VARCHAR(32) NOT NULL DEFAULT 'user'`
5. Data backfill: existing vocab items with `(token, language)` matching
   the 12 known starter tokens are set to `source='starter'`. Existing
   users get the default interest tags via the column default.

Down-migration drops all four new columns.

### API contracts

- `LLMClient.complete(prompt, response_schema, max_retries=3, *,
  system_prompt=None, max_tokens=None) -> T` — backwards-compatible
  extension.
- `generate_vocab_batch(llm, *, language, count, exclude_tokens,
  interests=None) -> GeneratedVocabBatch` — new pure function.
- `POST /settings/interests`: form body `tags: list[str]`. Validation:
  every tag must pass `is_valid_tag()`; reject with 422 on first
  unknown tag. Response: rendered partial with the saved tags.
- `POST /milestones/seen`: no body. Response: HTMX redirect to `/review`.
- Two new Celery task signatures:
  - `generate_shared_pool(count: int = 10) -> dict[str, int]` returning
    `{"vocab_created": N, "reviews_created": M}` on success or
    `{"skipped": "already_ran_today"}` or `{"succeeded": 0, "failed": 1,
    "reason": "validation_exhausted"}` on graceful failure.
  - `generate_personalized(user_id: str, count: int = 5) -> dict[str,
    int]` returning analogous shapes (with `"skipped":
    "already_fired_for_milestone"` for the idempotency short-circuit).

### Cost-control design (load-bearing — see decision log in `/Users/rizal/.claude/plans/we-should-add-the-happy-minsky.md`)

- **Exclusion list capped at 500 tokens**; DB unique constraint is the
  correctness gate. Comments at both sites explain why.
- **Both new tasks use `max_retries=2`** (not the default 3), capping
  blast radius at 2 LLM calls per task firing for transient errors.
- **`LLMValidationFailure` caught inside both task bodies**; returns
  graceful dict, does NOT re-raise. Celery treats `return` as success →
  no task-level retry → no second LLM call on a deterministically
  broken prompt.
- **Computed `max_tokens = count * 250 + 500`** for batch calls. Tighter
  cap than a static 4000; catches runaway completions earlier.
- **Source-column idempotency** for shared pool. Same-day check skips the
  LLM call entirely if a prior run already produced content today.
- **Milestone-column idempotency** for personalized. Same-milestone check
  skips the LLM call if the milestone was already serviced.

### Architectural decisions

- **Personalized is rate-endpoint-triggered, not beat-scheduled.** Beat
  would require scanning every user every cron tick. Rate-endpoint
  trigger fires exactly when meaningful (user actually crossed a
  milestone), with O(1) cost per rate request.
- **Celery `send_task` (string task name) instead of `.delay()`.** Avoids
  importing worker code into the API process. Loose coupling.
- **CSRF strategy**: `SessionMiddleware` is configured `same_site="lax"`
  (verified at `apps/api/app/main.py:33`). Browsers won't send the
  session cookie on cross-site POSTs, so CSRF for `/settings/interests`
  and `/milestones/seen` is mitigated without an additional token
  middleware.
- **Settings UI uses HTMX + the existing card-paper aesthetic.** No new
  JS framework. Matches the rest of the app.
- **Async generation lag accepted for V1.** User may hit `/dashboard`
  before the personalized worker finishes; banner appears on next
  refresh. HTMX polling is a future enhancement, not V1 scope.

## Testing Decisions

### What makes a good test

- **Test external behavior, not implementation details.** Assert on the
  return value, the data persisted, the HTTP response body, or the
  arguments passed to a mocked dependency — never on private function
  names or internal control flow.
- **Pure functions get unit tests.** Anything I/O-bound gets an
  integration test with the in-memory `sqlite+aiosqlite` engine and a
  mocked LLM (per existing pattern in
  `apps/api/tests/workers/test_content_gen.py`).
- **Mock the LLM at the `LLMClient` boundary, never the OpenAI SDK
  directly.** Keeps tests robust to SDK upgrades.

### Must-have test coverage

1. **`vocab_generation` service (deep module, pure)**
   - Prompt construction: SYSTEM_PROMPT includes the audience anchor,
     the exclusion list, and (when provided) the interests block.
   - Exclusion cap: passing 600 tokens yields a prompt with 500.
   - Empty interests omits the interests block but still produces a
     valid prompt.
   - `max_tokens` is computed as `count * 250 + 500` and passed to
     `LLMClient.complete`.
   - Returns the LLM's validated `GeneratedVocabBatch`.
   - Prior art: minimal — this is a new pure module. Pattern from
     existing schema tests in `apps/api/tests/schemas/` applies.

2. **`LLMClient` extensions (deep module surface)**
   - `system_prompt` is included as the first message when provided.
   - System message persists across refinement retries (not just the
     first attempt).
   - Per-call `max_tokens` overrides `self._max_tokens`.
   - Default behavior (no `system_prompt`, no `max_tokens`) is
     unchanged — verifies backwards compatibility for the existing
     `enrich_vocab_item` call site.
   - Prior art: existing LLM tests in `apps/api/tests/services/` if
     they exist; otherwise mirror the assertion pattern from
     `test_content_gen.py` for mocked OpenAI calls.

3. **Both new Celery tasks (orchestration, integration)**
   - `generate_shared_pool` happy path: inserts N `source='shared_pool'`
     vocab items, enrolls every user with a Review, returns expected
     counts.
   - `generate_shared_pool` same-day idempotency: second invocation in
     the same day returns `{"skipped": "already_ran_today"}` without
     calling the LLM (assert via mock call count = 0).
   - `generate_shared_pool` validation-exhausted: when `LLMClient.complete`
     raises `LLMValidationFailure`, the task returns the graceful failure
     dict and does NOT re-raise (verifies no Celery retry will fire).
   - `generate_personalized` happy path: inserts N `source='personalized'`
     vocab, enrolls ONLY the target user, updates
     `last_personalized_milestone`.
   - `generate_personalized` same-milestone idempotency: second
     invocation with `last_personalized_milestone` already at the
     current milestone returns the skipped dict without LLM call.
   - `generate_personalized` exclusion list includes user's existing
     review tokens (not just global vocab).
   - Prior art: `apps/api/tests/workers/test_content_gen.py` — already
     uses the `patch("app.workers.content_gen.SessionLocal",
     session_factory)` + `patch("app.workers.content_gen.LLMClient")`
     pattern. Extend the same file.

4. **User-data write boundaries (settings + milestone trigger)**
   - `POST /settings/interests` happy path with valid tags persists and
     returns the partial.
   - `POST /settings/interests` with at least one invalid tag returns
     422 and does NOT mutate the user.
   - `POST /settings/interests` requires authentication (401 when
     unauthenticated).
   - Milestone trigger in `/review/{id}/rate`: at total_reviews=30,
     `send_task` is called once with the right kwargs.
   - Milestone trigger does NOT fire at total_reviews=29 or 31.
   - Milestone trigger swallows Celery enqueue exceptions: a `send_task`
     that raises does not 500 the rate endpoint; the rate response is
     still 200 with the next card or done partial.
   - Prior art: `apps/api/tests/api/test_auth.py` (POST callback
     validation), `apps/api/tests/api/test_reviews.py` (rate endpoint
     test pattern). Extend `test_reviews.py` for the milestone trigger
     and create `test_settings.py`.

### Nice-to-have (not blocking)

- Dashboard banner template rendering test — assert the banner appears
  when `unseen_milestone is not None` and is absent otherwise.
- Migration 0004 up/down round-trip with backfill assertion (CI's
  Migration Check job covers basic up/down; explicit assertions on the
  backfill values are nice-to-have).

## Out of Scope

- **Multi-language generation.** Catalog is English-only per recent
  commits (`9151a91` "kid-friendly English words", `330f6de` "remove
  language selector"). VocabItem.language stays at "en" for all
  generated content.
- **In-session toast / live HTMX milestone animation.** Dashboard banner
  on next visit is V1; live in-review toast is a future enhancement.
- **HTMX polling on the dashboard banner.** User refreshes if they're
  excited; polling is post-V1.
- **Free-form interest tags.** Only the 14 curated `TOPIC_TAGS` are
  accepted. Future feature could let users propose tags subject to
  review.
- **Embedding-based dedupe.** Capped exclusion list + DB unique
  constraint is sufficient for current scale.
- **Fallback curated mini-pool on LLM total failure.** Silent zero is
  the V1 behavior. Multi-day failure detection is a future ops alert.
- **Per-user opt-out of shared pool.** Every user gets shared pool
  enrollment. Future preference toggle is post-V1.
- **Tag taxonomy versioning / rename migration tooling.** Manual
  migration is acceptable at current user count.
- **Forced-onboarding tag picker.** New users get sensible defaults; the
  Settings page is opt-in discovery.

## Further Notes

- **Auth/user-data rule** (from `apps/api/CLAUDE.md`): The migration,
  the settings route handler, the milestone trigger, and the User model
  changes touch user data. Per the project rule, these must be
  hand-written, not delegated to a generic subagent. Deep modules
  (`vocab_generation`, `interests`) and the LLM-client extensions don't
  touch user data and are fair game for delegation if desired.
- **Decision log**: Every cost-control decision (exclusion-list cap,
  max_tokens computation, idempotency markers, no-retry-on-validation,
  `max_retries=2`) traces back to grilling answers captured in
  `/Users/rizal/.claude/plans/we-should-add-the-happy-minsky.md`. That
  file is the source of truth for "why this choice"; this PRD is the
  source of truth for "what to build."
- **Existing patterns reused (no changes)**:
  - `_seed_starter_vocab` idempotent insert loop pattern (auth.py)
  - `SimpleVocabExample` Pydantic schema with validators
  - `contains_disallowed_term` content-safety check (via schema
    validators, applied automatically)
  - `LLMValidationFailure` + in-loop refinement retry (`llm.py`)
  - Existing `content_gen.run_daily` task pattern: sync wrapper +
    `asyncio.run(_async_impl)` + `SessionLocal` context manager +
    structured logging
  - Test fixtures from `apps/api/tests/workers/test_content_gen.py`
- **Expected annual cost**:
  - Shared pool: ~$0.25/year (1 LLM call/day, ~2500 output tokens).
  - Personalized: ~$0.05/user/month at moderate engagement.
  - Idempotency markers prevent 2× spend on Celery retries.
  - Both well within OpenRouter's free tier or pennies on pay-per-token.
