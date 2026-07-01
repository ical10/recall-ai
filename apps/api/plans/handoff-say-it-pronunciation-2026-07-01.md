# Handoff: fix "Say it" pronunciation check

Date: 2026-07-01
Repo: `/Users/rizal/GDrive/recall-ai` (branch `main`, solo project, push direct to main)

## Focus for next session
Implement the fix plan at `apps/api/plans/2026-07-01-say-it-pronunciation-fix.md`.
Read that plan first — it has the full root-cause analysis, the exact fixes, file
paths, test requirements, and ordering. This doc only adds live context not in the plan.

## Symptom
"Say it" button records voice fine, but on **Check** it fails immediately with no
feedback. Reported working on prod otherwise (audio autoplay + play button now work).

## State of debugging (not yet resolved)
Two candidate causes, both consistent with "immediate fail" — see plan §A/§B.
- **Not yet confirmed which.** The decisive check has NOT been run: prod →
  DevTools → Network → hit Check → read status on `/api/review/pronunciation`.
  - `503` → Cause A: STT env vars unset on the **web** service.
  - `500` → Cause B: Gemini JSON unparseable (fences), 100% fail.
- Prod logs alternative: `pronunciation not configured` (A) vs
  `invalid JSON from engine` (B).

## Key facts established this session
- STT config is a **separate** env set from TTS: `STT_PROVIDER`, `STT_API_KEY`,
  `STT_MODEL` (config fields at `apps/api/app/core/config.py:24-26`). The
  `VOICE_AGENT_*` vars (TTS) that were already set up do NOT cover STT.
- Backend flow is wired correctly: route `apps/api/app/api/json/pronunciation.py`
  (mounted via `app/api/json/__init__.py:17`), service
  `apps/api/app/services/pronunciation.py`, schema
  `apps/api/app/schemas/pronunciation.py`.
- Backend bug (Cause B): `evaluate_pronunciation` calls `json.loads(raw)` with
  no `response_mime_type="application/json"` and no fence stripping → latent
  100%-fail. Fix regardless of A/B (plan §1).
- Frontend swallows all non-503 errors silently — `apps/web/src/components/
  PronunciationGate.tsx` `handleSubmit`. No error UI (plan §3, Cause C).
- Recorder (`apps/web/src/hooks/useVoiceRecorder.ts`) and MIME handling are fine;
  blob is `audio/webm;codecs=opus`, route strips codecs → `audio/webm` (allowed).

## Recommended action
Ship plan §1 (Gemini JSON robustness) + §3 (frontend error surfacing) now —
correct regardless of which cause. Then confirm A via Network status; if 503,
set the three `STT_*` vars on the web service (plan §2, config-only).
Per repo rules: new/changed LLM-output boundary needs a happy-path + a
validation-failure test (plan "Tests" section).

## Done earlier this session (context only, already committed/pushed to main)
- `a6a84bb` fix(tts): decode Speechify base64 audio + re-raise on exhaustion.
- `3fcd920` test(tokens): fix flaky tamper test (last-char → first-char).
- Audio backfill run on prod worker; playback confirmed working. Not related to
  the pronunciation bug except that both share the "silent failure" anti-pattern.

## Repo conventions to honor (from CLAUDE.md)
- Pre-commit hook runs ruff + mypy strict + full pytest; all must pass. No bypass.
- Conventional commits. Commit trailers required (Co-Authored-By + Claude-Session).
- Plans live in `apps/api/plans/` (already done for this task).
- LLM output must validate through a pydantic schema (it does — keep it).

## Suggested skills
- `/diagnose` — if the Network/log check reveals a third cause, run the
  disciplined reproduce→instrument→fix loop before coding.
- `/plan` — only if scope grows beyond the existing plan (e.g. switching STT
  provider); otherwise the plan is ready to implement.
- `/review` — run on the change before it's considered done (repo workflow gate).
- `/verify` or `/run` — drive the app / prod review page to confirm "Say it"
  works end-to-end after the fix.
- `/session-end` — run before closing per global workflow rules.
