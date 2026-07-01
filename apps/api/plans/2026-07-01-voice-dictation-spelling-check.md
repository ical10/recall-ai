# Plan — Voice Dictation + Voice Spelling Checks (web SPA, critical path)

## Context
**Goal:** the RecallAI review flow should (1) **replay a vocab word's audio on demand** ("voice
dictation") and (2) let a child **speak a word and have AI judge whether they said it correctly**
("voice spelling check"). Target surface is the **web SPA** (`apps/web`) where review already runs;
the backend endpoint is surface-agnostic so the future extension reuses it.

**Current state (from exploration):**
- Audio *output* is built: `tts.py` (`synthesize`/`ensure_audio`) → R2 → `Card.word_audio_url` /
  `example_audio_url` → `GET /api/review/batch`. `apps/web` has `useAudioQueue` (`play`/`stop`) and
  auto-plays on reveal in `ReviewPage.tsx`. **Gap: no manual replay button.**
- Speech *input* is **fully greenfield** — no mic capture, no STT, no upload endpoints anywhere.
- Reusable seams: the `tts.py` engine-ABC + provider-registry pattern; `LLMClient`'s retry/validate/log
  loop (`services/llm.py`); `LLMOutput` + Pydantic validators (`schemas/llm.py`); `google-genai`
  (Gemini 2.5 Flash is **multimodal — accepts audio input**, so it can judge pronunciation). The text
  `LLMClient` (OpenRouter) cannot take audio → eval goes through a Gemini-style audio engine.

## Pinned decisions
- **Surface:** web SPA first (`apps/web`). Backend endpoint reusable by the extension later.
- **Placement:** pronunciation is **required before the rating buttons unlock**, with an always-present
  **Skip** (no mic / can't speak / accessibility). The verdict is a *gate + feedback only* — it does
  **not** set the SM-2 rating (SM-2 untouched; the child still self-rates Again/Hard/Good/Easy).
- **Recordings:** **discarded** after evaluation — never stored (no R2, no DB). Only the verdict is
  returned, transiently. Logs never contain audio (only target + byte length + verdict + latency).
- **Eval engine:** Gemini multimodal via `google-genai` (already a dep). New `stt_*` config trio
  (provider/key/model), mirroring `voice_agent_*`; the Gemini key may equal `voice_agent_api_key`.
- **Fail-open:** if `stt_provider` is unset OR the mic is unavailable/denied, the gate degrades to
  Skip-enabled so the app stays usable everywhere.

---

## Issue 0 — Profile fields create-only (cleanup; fold into PR #61 or a small follow-up)
`provision_user` overwrites `email`/`name`/`avatar_url` on **every** login — marginal gain, and a latent
clobber-trap once profile editing exists.
- **`apps/api/app/services/account.py`** — remove the 3 overwrite lines (the `if user is not None:`
  branch that re-assigns `user.email/name/avatar_url`); set those fields **only on create**.
- **`apps/api/tests/api/test_auth.py`** — `test_callback_handles_user_lifecycle` currently asserts an
  existing user's profile is updated to the new token values; flip it to assert they stay `old@b.com`/
  `"Old"` (profile is a first-login snapshot). Both web + extension login change together (correct).

## Issue A — Manual audio replay (completes "voice dictation"; web only, small)
The seam exists (`useAudioQueue.play()/stop()`); only UI is missing.
- **`apps/web/src/components/ReviewPage.tsx`** — in the `revealed` phase add a **replay button** (🔊)
  that calls `play([word_audio_url, example_audio_url])` again; optionally separate word vs example.
  Show a subtle playing/stop affordance (wire existing `stop()`). Guard when URLs are null (hide).
- Test: extend `ReviewPage.test.tsx` — replay button calls the queue with the card's URLs.

## Issue B1 — Pronunciation backend (the core net-new capability)
- **Config** `apps/api/app/core/config.py` (+ `.env.example`): add `stt_provider: str = ""`,
  `stt_api_key: SecretStr = SecretStr("")`, `stt_model: str = ""` (mirror `voice_agent_*`, no
  code-side default for model in prod). Document that the Gemini key may be shared.
- **Schema** `apps/api/app/schemas/pronunciation.py` (new) — `PronunciationVerdict(LLMOutput)`:
  `said_target: bool`, `heard: str` (what was transcribed), `confidence: float = Field(ge=0, le=1)`,
  `feedback: str = Field(max_length=200)` (kid-friendly). Validators: feedback required when
  `not said_target`; run `feedback`/`heard` through `contains_disallowed_term` (reuse
  `services/interests` / the denylist util used by `SimpleVocabExample`). Add happy + failure tests
  (project rule for new LLM-output schemas).
- **Service** `apps/api/app/services/pronunciation.py` (new) — mirror the `tts.py` seam:
  - `PronunciationEngine` ABC: `judge(audio: bytes, mime_type: str, *, target: str) -> str` (raw JSON).
  - `GeminiPronunciationEngine` via `google-genai`: `generate_content(model=stt_model,
    contents=[Part.from_bytes(audio, mime_type), prompt])`, prompt = "Did the speaker say the English
    word '{target}'? Reply JSON {said_target, heard, confidence, feedback}; feedback must be short,
    kind, and kid-appropriate." Provider registry + selection by `stt_provider`.
  - Orchestrator `evaluate_pronunciation(audio, mime_type, *, target) -> PronunciationVerdict`:
    retry/validate loop + structured logging (`pronunciation_eval`: target, bytes, attempts, latency,
    said_target — **never the audio**). Inject engine for tests (fake engine → fixed verdict).
- **Endpoint** in `apps/api/app/api/json/review.py`: `POST /api/review/pronunciation`, `UserDep`,
  multipart: `audio: UploadFile`, `vocab_item_id: UUID` (resolve the target token server-side from the
  user's `Review → VocabItem`; 404 if not the user's card). Validate **mime** (`audio/webm|mp4|wav`)
  and **size cap** (~2 MB; reject larger). Call
  `await asyncio.to_thread(evaluate_pronunciation, bytes, mime, target=token)` (sync engine off the
  loop, one interactive request — no Celery, no storage). Return `PronunciationVerdict`. If
  `stt_provider` unset → 503 `{detail: "pronunciation not configured"}` (frontend treats as Skip).
- **Dependency:** confirm/add **`python-multipart`** to `apps/api` deps (FastAPI requires it for
  `UploadFile`; no upload endpoints exist today, so it's likely missing → add to `pyproject.toml`).
- **Tests** (`apps/api/tests/`): service (fake engine → verdict; retry on bad JSON; disallowed-term →
  validation fail); endpoint (mocked engine → 200 verdict; oversize/bad-mime → 4xx; not-your-card →
  404; unset provider → 503; auth required). Never call real Gemini.

## Issue B2 — Pronunciation frontend (web SPA review gate)
- **`apps/web/src/hooks/useVoiceRecorder.ts`** (new) — `getUserMedia({audio:true})` + `MediaRecorder`;
  `{ start, stop, recording, blob, error, supported }`. Auto-stop after ~4 s; produce a `Blob`
  (`audio/webm`). On permission denied / unsupported → `supported=false` (drives fail-open Skip).
- **API client** (where `apps/web` calls `/api/review/*`): `postPronunciation(vocabItemId, blob)` →
  `FormData` multipart POST → `PronunciationVerdict`.
- **State** `apps/web/src/store/reviewSession.ts`: in `revealed`, add
  `pronunciation: "idle" | "recording" | "evaluating" | "passed" | "failed" | "skipped"`. Rating is
  **enabled only when `passed` or `skipped`**. Pass = `said_target && confidence >= 0.6` (tunable const).
- **`apps/web/src/components/ReviewPage.tsx`** (+ a small `PronunciationGate.tsx`): after reveal show
  **🎤 Say it** + **Skip**; rating buttons disabled until pass/skip. Record → `evaluating` spinner →
  verdict: ✅ "Nice!" (unlock) or 🔁 "Try again" + `feedback` (retry allowed). If `!supported` or 503,
  show Skip prominently (gate auto-open). Pronunciation never changes which rating the child picks.
- **Tests** (Vitest): recorder hook with a mocked `MediaRecorder`; store gating (rating locked until
  `passed`/`skipped`); `ReviewPage` shows verdict + unlocks; fail-open path when unsupported. Mock fetch.

---

## Cross-cutting
- **Privacy (kids):** audio is request-scoped and dropped after eval; nothing at rest; logs exclude audio.
- **Safety:** verdict `feedback`/`heard` pass the existing content denylist; prompt enforces kind,
  kid-appropriate tone (Novakid 5–12).
- **Cost/abuse:** size + mime caps; one eval per request; structured cost logging per call. (No rate
  limiter app-wide — same known gap as the auth endpoint; out of scope here.)
- **SM-2 untouched:** pronunciation gates the rating UI but is not a scheduling input.

## Verification
1. `pnpm lint` + `pnpm test` (Python) green — service + endpoint tests, all mocked (no real Gemini).
2. `apps/web` Vitest green — recorder hook, store gating, verdict UI, fail-open path.
3. **Live smoke** (manual, needs `STT_*` env): `pnpm dev`, review a card → 🔊 replays audio; 🎤 record
   the word → ✅ unlocks rating; record a wrong word → 🔁 + feedback; Skip unlocks; deny mic → Skip auto.
4. Per project rules: new schema has happy + failure tests; `python-multipart` added to the plan/deps;
   the audio endpoint handles user data but stores nothing (note in PR for review).

## Out of scope (later)
- Chrome extension surface (net-new frontend; reuses this endpoint).
- Storing recordings / pronunciation history / analytics (privacy-deferred).
- Phoneme-level scoring or a dedicated ASR provider (Gemini multimodal verdict is the v1).
- App-wide rate limiting.

## Next step
After approval: run **/handoff** to produce the handoff doc, and copy this plan to
`apps/api/plans/2026-07-01-voice-dictation-spelling-check.md` (per the project rule to keep finished
plans in the repo).
