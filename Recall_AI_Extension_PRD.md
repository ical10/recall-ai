# PRD: Recall-AI Modernization & Voice-First Extension

> **Framing.** This effort also serves as a portfolio showcase for an AI-voice-activation audience (spelling sounds, spelling checks), but
> the architecture choices are product-driven. The HTMX-over-React ADR was written for a
> *server-driven UI with no complex client state*; the product is now moving to a high-fidelity,
> interactive experience — clicks, animations, automatic voice playback, dictation, optimistic
> local state, instant re-renders — where that premise no longer holds. React supersedes that ADR on
> its own terms, not as a reversal-for-show. Postgres stays the single datastore (no Firebase): the
> workload has one writer per deck, so Firestore's real-time push buys nothing the app exercises.
> Recorded as a new ADR — see Implementation Decisions.

## Problem Statement

From the learner's perspective: reviewing vocabulary today means sitting at a web page and
*reading* cards. There is no hands-free, audio-first way to run a spaced-repetition session, and
nothing that lives in the browser where the learner already spends time. From the builder's
perspective: the current server-rendered HTMX/Jinja2 architecture has no JSON API surface, so it
cannot back a Chrome extension or any non-HTML client.

## Solution

Two phases:

1. **Phase 0 — Migration.** Replace the HTMX/Jinja2 frontend with a React 19 + TypeScript SPA
   (Tanstack Router + Query, Zustand, TailwindCSS retained), and convert the FastAPI Jinja2
   routes into Pydantic-powered JSON endpoints. End state: an API-first backend the extension can
   consume.

2. **Phase 1 — Voice-First Chrome Extension (Manifest V3).** A learner installs the extension and
   runs daily SM-2 reviews where each card's word is pronounced and its LLM-generated example sentence
   is **read aloud automatically on flip** — pre-rendered neural-TTS clips played through the Offscreen
   Documents API. Ratings sync back to the backend; the extension works offline by caching the daily
   batch (including clip URLs) locally and queueing ratings until reconnect.

## User Stories

### Phase 0 — Migration (functional parity)
1. As a learner, I want every screen I use today (dashboard, review, settings, archive) to work
   identically after the migration, so that nothing I rely on breaks.
2. As a learner, I want the review flow (show card → reveal → rate Easy/Good/Hard → next) to feel
   at least as fast as the HTMX version, so that the rewrite is not a regression.
3. As a learner, I want my existing account and review history intact after migration, so that my
   forgetting curve is preserved.
4. As a builder, I want every Jinja2 route replaced by a JSON endpoint with a Pydantic response
   schema, so that any client can consume the data.
5. As a builder, I want TypeScript interfaces generated from the Pydantic schemas, so that the
   frontend and backend cannot drift out of sync.
6. As a builder, I want a single centralized Tanstack Query API client for all CRUD, so that data
   fetching, caching, and invalidation are consistent.
7. As a builder, I want local UI state (current review session) in Zustand, so that the review
   flow does not require a server round-trip per interaction.
8. As a builder, once 1:1 parity is confirmed, I want all `.html` templates, `htmx`/`jinja2`
   dependencies, and legacy routes purged, so that there is no dead code.
9. As a builder, I want the Railway deploy updated for a decoupled frontend/backend build, so that
   the SPA and API ship cleanly.

### Phase 1 — Extension shell & auth
10. As a learner, I want to install the extension from the Chrome Web Store, so that reviews live
    where I browse.
11. As a learner, I want to sign in with Google inside the extension, so that I reach my own deck
    without re-entering credentials.
12. As a learner, I want my session to persist across browser restarts, so that I don't re-auth
    daily.
13. As a builder, I want auth via `chrome.identity.launchWebAuthFlow` exchanging a Google token
    with the backend, so that the extension uses the standard MV3 path.

### Phase 1 — Voice-first review
14. As a learner, I want each card read aloud automatically when it flips, so that I can review
    without reading.
15. As a learner, I want the LLM-generated example sentence read aloud too, so that I hear the word
    in context.
16. As a learner, I want to rate a card (Easy/Good/Hard) with a single click or keypress, so that I
    keep my hands free.
17. As a learner, I want audio to start within a fraction of a second of the flip, so that the
    session feels responsive.
18. As a learner, I want to pause/replay the audio for a card, so that I can hear a tricky word
    again.
19. As a learner, I want to browse and scroll my full vocabulary archive smoothly, so that reviewing
    my history never stutters.

### Phase 1 — Sync & offline
20. As a learner, I want a review I complete in the extension to immediately update my forgetting
    curve everywhere, so that web and extension agree.
21. As a learner, I want to start a review even with a flaky connection, so that a dropped network
    doesn't block me.
22. As a learner who reviews on web one day and the extension the next, I want my latest ratings to
    carry over, so that my forgetting curve is consistent across surfaces.
23. As a builder, I want the daily review batch delivered as one denormalized payload, so that the
    review session makes minimal reads.
24. As a builder, I want rating sync to be idempotent, so that a retried or duplicated sync never
    corrupts the SM-2 curve.

### Cross-cutting
25. As a learner who is an ESL kid, I want all generated content and voices to stay kid-appropriate,
    so that the experience matches the audience.
26. As a builder, I want any LLM call in the new surfaces to keep the existing timeout, retry, and
    token-cost logging guarantees, so that costs stay controlled.

## Implementation Decisions

### ADR changes (product-driven)
- **React 19 + TypeScript SPA replaces HTMX+Jinja2.** Supersedes the "htmx over next.js" ADR. That ADR
  assumed a server-driven UI with no complex client state; the product now requires high-fidelity
  interaction — automatic voice playback, dictation, animations, optimistic local state, instant
  re-renders — which server round-trip-per-interaction can't deliver well. The API-first surface this
  produces is also the prerequisite for the extension. Recorded as a new ADR superseding the original.
- **Postgres stays the single datastore — Firebase rejected.** The source PRD floated Firestore for
  real-time multi-device sync. But the workload has exactly one writer per deck (the learner, one
  device at a time), so Firestore's real-time push is never exercised; the cost would be a second
  datastore, a second auth surface, and dual-write reconciliation. Postgres-only wins on the latency
  that matters (client → FastAPI → Postgres is one intra-datacenter hop) and on simplicity, and keeps
  the existing Postgres-only ADR intact. Offline is handled client-side (see sync module) rather than
  by a synced datastore. Firebase revisit trigger: genuine concurrent multi-user editing or
  multi-region low-latency reads — neither present today.

- **Pre-rendered neural audio; Speechify SIMBA 3.0 as the voice.** Card audio (word pronounced, then
  example sentence) is rendered once per card during the content pipeline and replayed forever, so
  cost scales with new cards (~100/mo/user ≈ 15k chars), not reviews. Pronunciation accuracy *is* a
  functional requirement for ESL learners, so voice quality drives the engine choice. The default is
  **SIMBA 3.0**: streaming-native (low first-byte latency, matters for auto-play-on-flip), top-tier
  voice quality, SSML prosody control, and competitive cost at $10/M chars ≈ **$0.15/mo at this
  volume**. Strict-$0 alternative: **Google Gemini Flash TTS** (free tier covers the volume).
  Self-hosted offline fallback: **Piper** in the Celery worker (no quality guarantee). Clips stored on
  a **Railway volume**, served via the existing `/static` handler with `Cache-Control`; storage
  upgrade if bandwidth grows is Cloudflare R2 (free egress). The render step sits behind a
  `synthesize(text) -> url` seam, so the engine swaps without touching callers. No letter-by-letter
  spelling needed — straight word + sentence pronunciation.

### Modules to build/modify
- **SM-2 scheduler** (backend, exists): pure scheduling function. Reused unchanged; the curve math
  is the contract the whole system protects.
- **Daily-batch builder** (backend service, new): given a user, produces the day's review batch as a
  single denormalized JSON payload. Interface: `build_daily_batch(user) -> DailyBatch` (Pydantic).
- **Rating sync service** (backend service, new): accepts a batch of SM-2 ratings and applies them
  **idempotently** (each rating carries a client-generated id; re-applying is a no-op). Interface:
  `apply_ratings(user, ratings) -> SyncResult`.
- **JSON endpoint layer** (backend): each former Jinja2 route becomes an `async` endpoint returning a
  Pydantic model. No `TemplateResponse` outside the legacy code being deleted.
- **Pydantic→TypeScript type generation** (build tooling): one generation step produces TS interfaces
  from the response schemas; checked into the frontend and verified by `tsc`.
- **Tanstack Query API client** (frontend): centralized client for all CRUD; thin wrapper, owns
  caching/invalidation keys.
- **Review-session store** (frontend, Zustand): state machine `idle → showing → revealed → rating →
  next`, holding the current batch in memory. This is the heart of the client UX.
- **Audio render step** (backend, in the content pipeline / Celery worker, new): after content is
  generated and Pydantic-validated, render TTS clips for the word (spelled) and the example sentence
  via the TTS engine (default Speechify SIMBA 3.0; Google Gemini Flash TTS for strict-$0; Piper as
  self-hosted fallback), store them on the Railway volume, and persist the clip URLs on the card.
  Idempotent — skip if a clip already exists for that card+text (no duplicate LLM/TTS spend). Behind a
  `synthesize(text) -> url` interface so the engine can be swapped without touching callers.
- **Audio player** (extension, Offscreen Documents API): plays the pre-rendered clip URLs (word, then
  example) on flip. Behind an interface (`play(url) / stop()`) so the offscreen/browser binding is
  swappable and the calling logic is testable without a browser.
- **`chrome.identity` auth** (extension): `launchWebAuthFlow` → Google token → exchanged with backend
  for a session. **Hand-written and manually reviewed** per the project auth rule; no AI-authored
  auth accepted as-is.
- **Offline rating queue** (extension): caches the daily batch in `chrome.storage`/IndexedDB and
  queues ratings locally, flushing through the idempotent `POST /api/review/ratings` endpoint on
  reconnect. No second datastore — durability comes from the idempotent server endpoint. Interface:
  `enqueue(rating) / flush()`.
- **Archive view** (frontend): a plain rendered (paginated) list. At ~100 cards/month a user stays in
  the hundreds for a year+, which renders at 60FPS without virtualization. *ponytail: add `react-window`
  only when a single user's archive crosses ~1k cards — deferred, not built now.*

### API & data contracts
- `GET /api/review/batch` → `DailyBatch` (denormalized: cards + generated examples + scheduling
  metadata + pre-rendered audio clip URLs for word and example).
- `POST /api/review/ratings` → `SyncResult`; body is a list of `{rating_id, card_id, grade, rated_at}`;
  idempotent on `rating_id`.
- All request/response bodies and all LLM-output boundaries keep Pydantic v2 schemas (existing rule).
- Postgres is the single source of truth for SM-2 state. The extension's local queue is a transient
  client-side buffer, not a second store — the server endpoint's idempotency is what guarantees no
  lost or double-applied ratings.

### Auth
- Extension: `chrome.identity.launchWebAuthFlow` with `identity` permission; token exchanged for the
  same backend session the web app issues. Set `SESSION_HTTPS_ONLY=true` in prod.

## Testing Decisions

**What makes a good test here:** assert external behavior through a module's public interface, not
its internals. Prior art: the existing `apps/api/tests/` pytest suite mirroring `app/` structure,
and the existing rule that every Pydantic schema ships one happy-path and one validation-failure
test.

**Modules to test:**
- **SM-2 scheduler** — input grade + prior state → next interval/ease. Pure, fully covered. (Reuse
  existing tests; extend if interface changes.)
- **Daily-batch builder** — given a seeded user, the batch contains the expected due cards and shape.
- **Rating sync service** — *idempotency is the headline test*: applying the same `rating_id` twice
  leaves the curve identical to applying it once; out-of-order ratings reconcile deterministically.
- **Review-session store** (frontend) — the state machine: illegal transitions rejected, a full
  show→reveal→rate→next cycle advances correctly. No DOM, just the store.
- **Offline rating queue** — ratings made offline are queued and flush exactly once on reconnect; a
  flush interrupted mid-way replays safely against the idempotent endpoint with no double-apply.
- **Audio render step** — a card with no existing clip gets one generated and its URL persisted;
  re-running the step for an already-rendered card is a no-op (no duplicate spend). Test against the
  `synthesize` seam, not real audio output.
- **New Pydantic schemas** (`DailyBatch`, rating payload, `SyncResult`) — happy-path + validation-failure each.

**Not deep-unit-tested:**
- Audio player — browser/Offscreen-bound; test the calling logic against the `play/stop` seam, not
  real audio.
- Tanstack Query client — thin wrapper; covered by the endpoint tests it calls.
- TS type generation — verified by `tsc` compiling, not a test.

## Out of Scope
- Mobile native apps (iOS/Android); the extension + web SPA are the only surfaces.
- Replacing SM-2 with FSRS (separate candidate decision).
- New LLM content *types* — generation pipeline is unchanged; this PRD only changes how content is
  delivered and voiced.
- Offline *content generation*; offline applies only to running a pre-fetched review batch.
- Non-Chromium browsers for the extension.

## Further Notes
- **Risk: big-bang rewrite on a solo project.** Phase 0 must reach confirmed 1:1 parity *before* the
  legacy purge; keep the HTMX app deployable until parity is signed off.
- **Audience tension:** the project's stated audience is ESL kids 5–12, but a self-installed Chrome
  extension is an adult/power-user surface. For the portfolio goal this is acceptable; if it ever
  goes to real young users, revisit who installs and operates it.
- **Cost guardrails unchanged:** every LLM call in new surfaces keeps timeout + retry + token-cost
  logging; no Celery retry on validation failures.
- **DoD (from source PRD):** SPA with zero HTMX/Jinja2 left; every extension card read aloud;
  60FPS archive scroll; initial review load <500ms; extension rating updates the backend SM-2 curve.
- **Why the perf targets:** voice-first review demands near-instant audio-on-flip; per-interaction
  HTMX server round-trips would be janky. The architecture delivers the targets directly — the daily
  batch preloads into client (Zustand) state and TTS plays locally, so flip→audio and rate→next never
  hit the network. `<500ms` is the one-time batch load; `60FPS` is local rendering. Measure these on
  the new app against the targets (no HTMX baseline needed — HTMX is what we're leaving).
