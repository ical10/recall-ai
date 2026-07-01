# Plan: auto-check pronunciation (remove the manual "Check" button)

Date: 2026-07-01
Status: proposed
Scope: frontend only, one file.

## Context
The "Say it" flow currently has two steps after recording: the recording stops
(→ `ready` state), then the user must click a separate **📤 Check** button to
send the audio for evaluation. The user wants the check to happen automatically
once recording stops — no extra button whose only job is "submit for checking".

This is a UX-only change; it does not touch the backend eval or the separate
bug/plan `apps/api/plans/2026-07-01-say-it-pronunciation-fix.md` (which fixes the
check *failing*). Ship order: fix the failure first, then this. This plan assumes
the check works.

## Change
File: `apps/web/src/components/PronunciationGate.tsx`

1. **Auto-submit on stop.** Add a `useEffect` that calls `handleSubmit()` when
   `recorder.state === "ready"` and `recorder.blob` is present and we're not
   already `checking` and have no `verdict` yet. Deps: `[recorder.state,
   recorder.blob]`. Guard with the `checking`/`verdict` conditions to prevent a
   double-submit (React strict-mode double-invoke, or re-render).
   - `handleSubmit` already early-returns if `!recorder.blob`, so it's safe.
   - Recording already auto-stops after 4s (`useVoiceRecorder.ts` timer) or via
     the Stop button → both land in `ready` → both now auto-check.

2. **Drop the Check button.** In the `recorder.state === "ready" && !checking`
   block, remove the `📤 Check` primary button. Keep **🔁 Retry** and **Skip**
   there so that if the auto-check fails (or the child wants a redo), they can
   re-record without a dead-end. The `Checking pronunciation...` block already
   covers the in-flight state.

Resulting flow: `idle` (🎤 Say it) → `recording` (Stop) → auto → `Checking…` →
verdict (✅ advance, or 🔁 feedback + Retry/Skip).

## Reuse
- No new state or deps needed beyond existing `checking`, `verdict`, and
  `recorder.{state,blob}`. `handleSubmit` is reused as-is.

## Out of scope
- Silence auto-detection / VAD (keep the manual Stop + 4s timeout).
- Error-surfacing on failure — tracked in the pronunciation-fix plan §3.

## Verification
- `pnpm --filter web test` — extend the existing gate/`ReviewPage` RTL test:
  after the recorder reaches `ready`, assert the fetch to
  `/api/review/pronunciation` fires without a Check click, and that no "Check"
  button is rendered.
- Manual: prod/dev review card → 🎤 Say it → speak → Stop → it should show
  "Checking…" immediately and then the verdict, with no intermediate Check step.

## Post-approval housekeeping
- Copy this plan into `apps/api/plans/` with a dated kebab filename (repo
  convention) once implementation starts.
