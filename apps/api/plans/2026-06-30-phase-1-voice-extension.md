# Plan — Phase 1: Voice-First Chrome Extension (#45–49)

## Context

Phase 0 shipped: API-first FastAPI backend + React SPA, all merged to `main`. Phase 1 (epic #37) is
the **voice-first Manifest V3 Chrome extension** plus the **backend TTS render step** that feeds it.
Five issues: #45 audio render (backend), #46 extension shell, #47 auth bridge (HITL), #48 voice
review, #49 offline queue.

The groundwork is already in place: `DailyBatch.Card` carries nullable `word_audio_url` /
`example_audio_url` (forward-declared in Phase 0), `POST /api/review/ratings` is idempotent on
`rating_id` (the offline-sync contract), and `GET /api/me` exists. Phase 1 populates the audio URLs
and builds the extension that consumes them.

## Current state (verified)
- `app/models/vocab_item.py`: **single** `audio_url: str | None` (1024) — no word/example split yet.
- `app/services/daily_batch.py:50-51`: `word_audio_url=None, example_audio_url=None` (hardcoded).
- `app/workers/content_gen.py`: Celery tasks `run_daily`, `generate_shared_pool`,
  `generate_personalized[_for_all]`; `_persist_batch_and_enroll` helper. Content is LLM-generated →
  Pydantic-validated → persisted here; the audio step hooks **after** persist.
- `app/services/llm.py`: `complete(..., max_retries=3, timeout_s=30, max_tokens)` with structured
  logging — **the pattern the `synthesize()` seam mirrors**.
- `app/core/config.py`: `LLM_*` trio are required env vars with no code default — the model for `TTS_*`.
- `apps/`: only `api` + `web`. No `apps/extension`. `pnpm-workspace.yaml` globs `apps/*` + `packages/*`.
- No TTS / audio / offscreen code anywhere — all net-new.

## Cross-cutting decisions (pin before building)

1. **Extension lives at `apps/extension/`** — new pnpm workspace, Vite + TypeScript MV3 (CRXJS plugin
   or plain Vite multi-entry). *ponytail: one new app package, mirrors `apps/web`.*
2. **Shared API types.** Move the `openapi-typescript` output into the empty `packages/shared/`
   (`gen:types` → `packages/shared/api-types/schema.d.ts`); both `apps/web` and `apps/extension`
   import it. Single source of truth, no drift. (Small refactor of the existing `gen:types` script.)
3. **`synthesize(text) -> AudioClip` seam** mirroring `services/llm.py`: timeout + retry + **char/cost
   logging**, env-selectable engine behind an interface. Env: **`VOICE_AGENT_API_KEY`** (the provider
   key, no code default) + **`VOICE_AGENT_PROVIDER`** (`gemini` | `piper` | `speechify`) selecting the
   engine. Same dev/prod split as the LLM trio:
   - **dev** → `gemini` (Gemini Flash TTS, free tier — key from Google AI Studio) or `piper` (local
     binary + `.onnx` voice, **no key needed**) — don't burn Speechify credits while building.
   - **prod** → `speechify` (**SIMBA 3.0**, paid key).
   - `VOICE_AGENT_API_KEY` is required for `gemini`/`speechify`, **unused/empty for `piper`**.
   - **voice:** pick a **kid-appropriate** voice (Novakid 5–12 audience) — a config knob, not hardcoded.
   - No Celery retry on a validation/synthesis failure — log + fall back (cost guardrail).
4. **Storage = object storage (Cloudflare R2), NOT a Railway volume — decided.** The worker renders and
   the web/clients serve, and **Railway volumes mount to a single service** (a worker-written volume is
   invisible to web). R2 is reachable by both; clients fetch the URL **directly** (bandwidth off
   FastAPI), it's **durable** (a lost volume = re-paying TTS), and **R2 egress is $0**. The
   `synthesize()` seam returns the final URL, so callers don't care where it lives. *Rejected
   alternative: lazy render-in-web + volume — degrades audio-on-flip latency and loses pre-render cost
   control.*
5. **Audio columns.** Migration: add `word_audio_url` + `example_audio_url` to `VocabItem`; drop the
   unused single `audio_url`. One alembic migration.
6. **Idempotent render** — skip a card that already has both clip URLs (no duplicate TTS spend).
7. **Extension auth = bearer token, not the cookie.** The SPA uses the same-origin session cookie; the
   extension is cross-origin, so #47 issues a **token** the extension stores in `chrome.storage` and
   sends as `Authorization: Bearer`. The backend `current_user` dep must accept *either* the session
   cookie (web) *or* a bearer token (extension). **HITL — hand-written + audited** per project rule.
   *Auth specifics (token format JWT-vs-opaque, Google-token JWKS verification, the extension's own
   Google OAuth client) are deferred to #47 since it's hand-written anyway — see #47.*
8. **Extension surface = side panel** (`chrome.sidePanel`), not the popup. A popup closes on
   click-away, which kills a hands-free review session; the side panel persists alongside the page.

## Build order (DAG)

```
#45 audio render (backend) ──→ [Phase 1a: web SPA plays audio]  ← de-risk gate
#46 extension shell ── #47 auth (HITL) ──┐
                                          └─→ #48 voice review ─→ #49 offline queue
```
- **#45 and #46 start in parallel** (independent: backend vs extension scaffold).
- **Phase 1a (de-risk, do right after #45):** wire audio auto-play-on-flip into the **web SPA** review
  (`apps/web`). This validates the whole audio path — render → R2 → `DailyBatch` → browser playback —
  with **zero** MV3/offscreen/auth complexity, and ships voice-first on web as a bonus. Only then build
  the extension playback (#48), porting the validated behavior.
- #47 after #46. #48 needs #45 (audio URLs) + #47 (auth). #49 after #48.

---

## #45 — Pre-rendered audio render step (backend, Celery)

- **Migration**: `VocabItem` → add `word_audio_url`, `example_audio_url` (nullable); drop `audio_url`.
- **`app/services/tts.py`** — `synthesize(text: str, *, voice: ...) -> str` (returns clip URL). Mirror
  `llm.py`: timeout, `max_retries`, char-count + cost structured logging. Engine behind an interface
  (`SpeechifyEngine`, `GeminiEngine`, `PiperEngine`), selected by `VOICE_AGENT_PROVIDER`. Uploads bytes
  to R2, returns the public URL.
- **`app/core/config.py`**: add `VOICE_AGENT_API_KEY` (no default; empty when provider=piper) +
  `VOICE_AGENT_PROVIDER` + R2 creds.
- **Engine**: dev → Gemini Flash / Piper; prod → SIMBA 3.0; kid-appropriate voice (decision #3).
- **Render hook** in `content_gen.py`: after a card is generated + validated + persisted, render the
  **word** clip then the **example sentence** clip, persist both URLs. **Idempotent** — skip if both
  exist. A new task `content_gen.render_audio(vocab_item_id)` (or inline in the persist path), enqueued
  per new card. No Celery retry on synth failure → log + leave URLs null (card still reviewable, silent).
- **Backfill (don't skip):** the hook only catches *new* cards — every existing card (starter vocab +
  already-generated pool) has no audio, so review would be silent for current decks. Add a one-off
  `content_gen.backfill_audio` task that renders clips for all enriched cards missing them (idempotent,
  reuses `render_audio`). Run it once after deploy; safe to re-run.
- **`build_daily_batch`**: read `word_audio_url`/`example_audio_url` from the model instead of `None`.
- **Tests**: render produces + persists 2 URLs; re-running is a no-op (assert against the `synthesize`
  seam, not real audio); backfill renders only the missing ones; `DailyBatch` returns populated URLs;
  cost/timeout/retry logging present.

## Phase 1a — Web SPA plays audio (de-risk gate, right after #45)

Before touching the extension, prove the audio pipeline on the existing React review:
- In `apps/web` review, on flip auto-play the `word_audio_url` then `example_audio_url` from the batch
  (a small `useAudioQueue` hook + an `<audio>` element; preload the next card's clips).
- Add a pause/replay control. This is plain DOM audio — no MV3, no offscreen, no new auth.
- **Outcome:** voice-first works on web, validating render → R2 → batch → playback end-to-end. #48
  then ports this exact behavior into the extension's Offscreen player.

## #46 — Extension shell (MV3)

- Scaffold `apps/extension/`: `manifest.json` (MV3; permissions `identity` + `offscreen` +
  `sidePanel`; `host_permissions` for the API origin), background **service worker**, a **side panel**
  UI (decision #8; React), typed API client importing `packages/shared/api-types`.
- Refactor `gen:types` → `packages/shared` (decision #2); both apps consume it.
- No auth yet: a no-auth call (`GET /healthz` or `/api/me` returning 401) proves the wiring.
- **DoD**: loads unpacked in Chrome, service worker runs, side panel opens + renders, shared types compile (`tsc`).

## #47 — Extension auth bridge (chrome.identity) — **HITL / hand-written**

- Extension: `chrome.identity.launchWebAuthFlow` → Google OAuth → Google token.
- Backend: `POST /api/auth/extension` verifies the Google token, finds/creates the user, issues a
  **backend bearer token** (signed, e.g. itsdangerous/JWT). Extend the `current_user` dep to accept
  `Authorization: Bearer` *or* the session cookie.
- Extension stores the token in `chrome.storage`, attaches it to all API calls; persists across
  restarts. `SESSION_HTTPS_ONLY=true` in prod.
- **Hand-written + manually audited; not AFK-agent merged.** Tests: token issue/verify, authed call
  returns the right user, unauth → 401.

## #48 — Voice-first review session (extension)

- Service worker fetches `GET /api/review/batch` (now with audio URLs) for the signed-in user.
- Review UI: show card → on flip, an **Offscreen Documents** audio player auto-plays the **word** clip
  then the **sentence** clip. Behind a `play(url) / stop()` seam so calling logic is testable without a
  browser. Audio starts within a fraction of a second (preload next card's clips).
- Easy/Good/Hard via click + keypress → record rating → advance. Pause / replay control.
- Reuse the Zustand review-session state-machine shape from `apps/web` (port, not share — different app).
- **Tests**: player auto-plays word→sentence on flip (against the `play/stop` seam); rate advances +
  submits to the idempotent endpoint; pause/replay.

## #49 — Offline rating queue + sync (extension)

- Cache the daily batch (incl. clip URLs) in `chrome.storage`/IndexedDB → a session starts offline.
- Queue ratings locally; flush through the **already-idempotent** `POST /api/review/ratings` on
  reconnect. Interface `enqueue(rating) / flush()`. An interrupted flush replays safely (idempotent on
  `rating_id`) — no double-apply. Cross-surface: extension ratings reflect on web.
- **Tests**: enqueue + flush-once + interrupted-flush-replays (the headline), all against the seam.

---

## Cost guardrails (LLM/TTS — project rule)
Every TTS call: timeout + retry + **char/cost logging**; render is **idempotent** (skip rendered
cards); **no Celery retry on synth/validation failure** (log + fall back, don't burn spend retrying).
Same discipline as the LLM pipeline.

## Verification (end-to-end)
1. Backend: `pnpm lint` + `pnpm test`; new TTS + render tests green; trigger content gen → cards get 2
   clip URLs in R2; `GET /api/review/batch` returns them.
2. Extension: `pnpm --filter extension build`; load unpacked in Chrome; sign in (chrome.identity);
   run a review — word + sentence auto-play on flip; rate Easy/Good/Hard → persists (check dashboard).
3. Offline: go offline mid-session → keep reviewing; reconnect → queued ratings flush exactly once;
   confirm the SM-2 curve matches web.
4. DoD (PRD): every card read aloud; audio-on-flip < a fraction of a second; extension rating updates
   the backend SM-2 curve; offline review works.

## Decided (folded in)
- **Storage**: Cloudflare R2 (decision #4). **TTS engine**: dev → Gemini Flash/Piper, prod → SIMBA 3.0,
  kid voice (decision #3). **Extension surface**: side panel (decision #8). **Sequencing**: #45 →
  Phase 1a web-audio de-risk → extension. **Backfill** existing cards' audio (in #45).

## Provisioning needed (external, before the relevant issue)
- **R2 bucket + access keys** (before #45).
- **`VOICE_AGENT_API_KEY`**: dev = Gemini key from Google AI Studio (aistudio.google.com/apikey, free
  tier) **or** Piper (no key — local binary + `.onnx` voice); prod = Speechify/SIMBA key. Set
  `VOICE_AGENT_PROVIDER` to match.
- **#47 (HITL):** decide token format (JWT vs opaque), add Google-token **JWKS verification**, and
  create the extension's **own Google OAuth client** (chrome-extension redirect URI) — resolved when we
  build #47, since it's hand-written + audited anyway.
- To-issues: these 5 issues exist (#45–49); fix any stale `Blocked by` links (#48 was empty earlier).
