# Plan: fix "Say it" pronunciation check failing immediately

Date: 2026-07-01
Status: proposed

## Symptom
"Say it" records voice fine, but on Check it fails immediately with no feedback.

## Root causes (confirm which via Network tab status / prod logs)

- **A. STT unconfigured → 503.** `STT_PROVIDER`/`STT_API_KEY`/`STT_MODEL` are a
  separate env set from the `VOICE_AGENT_*` (TTS) vars. Empty provider → route
  returns 503 → frontend silently advances the card.
- **B. Gemini JSON unparseable → 500 (100% fail).** `evaluate_pronunciation`
  calls `json.loads(raw)` with no `response_mime_type` and no fence stripping.
  Gemini wraps JSON in ```json fences / prose → every attempt throws → 500.
- **C. UX gap (independent).** Frontend swallows all non-503 errors with no
  message, so both A and B look like a mysterious instant fail.

## Fixes

### 1. Force JSON from Gemini + tolerate fences (fixes B) — `app/services/pronunciation.py`
- Pass `config=GenerateContentConfig(response_mime_type="application/json")` on
  the `generate_content` call so Gemini returns bare JSON.
- Belt-and-suspenders: before `json.loads`, strip a leading/trailing ```json …
  ``` fence if present. One small helper, one branch.
- No schema/behaviour change to `PronunciationVerdict`.

### 2. Config check (fixes A) — no code
- Set `STT_PROVIDER=gemini`, `STT_API_KEY=<gemini key>`,
  `STT_MODEL=gemini-2.5-flash` (an audio-capable model) on the **web** service.
- Document these in the deploy notes alongside the `VOICE_AGENT_*` set.

### 3. Surface errors in the UI (fixes C) — `apps/web/src/components/PronunciationGate.tsx`
- Add an `error` state. On non-ok (non-503) or thrown fetch, set a short
  kid-friendly message ("Hmm, couldn't check that — try again") and keep the
  Retry/Skip buttons visible instead of returning silently.
- Keep the 503 fail-open behaviour (skip) but log it.

## Tests
- `app/services/pronunciation.py`: unit test that a fenced ```json response
  parses to a valid `PronunciationVerdict` (happy path) and that a non-JSON
  response still raises after retries (failure path). Mock the engine — no
  network. Satisfies the "new/changed LLM-output boundary needs a happy + a
  failure test" rule.
- Frontend: extend `ReviewPage`/gate test to assert an error message renders on
  a 500 response (if the gate is covered by existing RTL tests).

## Out of scope
- Retry/latency tuning, switching STT providers, streaming.
- Dead `ALLOWED_MIMES` constant in the route is unused; delete opportunistically.

## Order
1. Confirm A vs B from Network status / logs.
2. Ship fix #1 (JSON robustness) regardless — it's a latent 100%-fail bug.
3. Set STT env vars if 503 (fix #2).
4. Ship fix #3 (error surfacing) so the next failure isn't invisible.
