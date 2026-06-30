# Architecture Deepening — Auth seam + Content pipeline (handoff)

> From an `/improve-codebase-architecture` review. Three deepening opportunities, grilled and
> crystallized. **#3 + #2 are do-first** — they cleanly unblock #47 (extension auth) instead of
> bolting it on insecurely. Vocabulary: a **deep module** = lots of behaviour behind a small
> **interface**; a **seam** is where behaviour can be swapped via **adapters** without editing in place.

## #3 — Verified Google identity (a deep verification seam) — SECURITY

**Why:** `api/auth.py:161-168` base64-decodes the Google `id_token` **without verifying the signature**
(masked today because the web token comes server-to-server). #47 will accept a token *from the
extension client* — verifying it by copying this inline pattern would be an **auth bypass**.

**Module:** `app/services/google_identity.py`
- **Interface:** `verify_google_id_token(raw: str) -> GoogleIdentity` (raises `InvalidGoogleToken`).
  `GoogleIdentity` = frozen value: `sub`, `email`, `name`, `picture`.
- **Behind the seam:** `google-auth`'s `google.oauth2.id_token.verify_oauth2_token(raw, Request())`
  (JWKS fetch + rotation + signature + `iss`/`exp`), then assert `claims["aud"] ∈ {google_client_id,
  google_extension_client_id}`. (Decided: `google-auth`, not hand-rolled JWKS.)
- **Scope (decided): verify only.** Find-or-create-User + starter seed stay in the handlers.
- **Config:** add `google_extension_client_id: str = ""` (`app/core/config.py`). **Dep:** `google-auth`.
- **Callers:** `/auth/callback` replaces lines 161-168 with one call; the #47 `POST /api/auth/extension`
  uses the same seam.
- **Tests:** verifier rejects forged-signature / expired / wrong-`iss` / `aud`-not-allowed, accepts
  valid; callback/extension tests **mock the seam** (no hand-built JWTs).

## #2 — Authentication as a real seam (session + bearer adapters)

**Why:** `api/deps.py:13-20` `get_current_user` hardcodes `request.session["user_id"]` — shallow, not a
seam. The extension authenticates with a **bearer token**; adding it today = in-place edits on the path
every endpoint depends on.

**Module:** `app/api/deps.py` (+ a small token signer)
- **Interface unchanged:** `UserDep` / `get_current_user(request, session) -> User` (401 on none). All
  handlers stay as-is — that's the leverage.
- **Behind the seam:** ordered **adapters**, each `resolve(request, session) -> User | None`:
  - `BearerTokenAdapter` — reads `Authorization: Bearer <token>`, validates, returns User.
  - `SessionCookieAdapter` — today's session-cookie logic.
  Resolver returns the first hit, else 401.
- **Bearer token (decided):** **itsdangerous-signed**, stateless (`URLSafeTimedSerializer` on
  `SECRET_KEY`, carries `user_id`), **~30-day** lifetime (PRD: persist across restarts). No new table.
  `itsdangerous` is already a dep. Put sign/verify in e.g. `app/core/tokens.py`.
- **Issued by:** `POST /api/auth/extension` (#47) — verify Google identity (#3) → find/create User →
  mint the 30-day token. Set `SESSION_HTTPS_ONLY=true` in prod.
- **Tests:** each adapter in isolation (valid / absent / garbage); resolver ordering + 401 once.
- **HITL:** auth code — hand-written + audited per project rule.

## #1 — Deepen the content pipeline (shrink the god-procedure)

**Why:** `workers/content_gen.py` orchestrates the whole **Enrichment**/generation lifecycle inline
across 6 tasks — the per-item Enrichment state transition, dedup-insert, and **Enrollment** all live in
the worker; `enrichment.py`/`vocab_generation.py` are shallow pure functions whose real behaviour is in
*how* the worker calls them (no **locality**).

**Shape (decided): deepen the step modules; the worker becomes thin entry points.**
- **`enrichment.py` owns the full `pending → ready` transition for one Vocab Item** — LLM call + mutate
  `definition`/`example_sentence` + reset/track `enrichment_attempts` + stamp
  `last_enrichment_attempted_at` (ADR-0005), empty-string sentinel (ADR-0001). Not just the LLM call.
- **New `app/services/enrollment.py`** owns **Enrollment** (now in `CONTEXT.md`): persist a new shared
  Vocab Item (dedup on `(token, language)` via the unique constraint) + create one **Review** per user.
  Replaces the unnamed `_persist_batch_and_enroll`.
- **`content_gen.py` collapses** to thin Celery tasks that sequence these + `asyncio.run` them
  (**ADR-0003 preserved** — `asyncio.run`, not a sync engine).
- Audio render calls the #4 "ensure audio for this Vocab Item" seam (idempotency in the seam).
- **Tests:** Enrichment transition + Enrollment dedup/idempotency each tested through their own small
  interface, instead of asserting scattered mutations inside Celery tasks.

## Related (smaller, from the same review)
- **#4** audio idempotency → move the "skip if already rendered" guard into the `tts` seam (one place,
  not duplicated in `content_gen`).
- **#5** make `due.py` the single home for "due / reviewed-on-a-local-day" (streak logic in `stats.py`
  reimplements timezone SQL).
- **#6** ORM→response serialization seam (`from_attributes`) to kill manual tuple-unpacking drift.
- Cleanups: mis-scoped `GET /vocab` (lists all Vocab Items, ignores user) vs `/api/archive`;
  un-`urlencode`d consent URL (`auth.py:52`); `ReviewState`≅`ReviewUpdate`; `ReviewState.from_review`.
- **Doc drift to confirm:** the **Again Re-queue** (ADR-0002 / CONTEXT.md) was the legacy HTMX
  session-cookie mechanism — the React/JSON review path (`daily_batch`) has no again-requeue, so it
  looks **dead** post-#44. Confirm + update docs (not a refactor).

## New dependency
- `google-auth` (for #3). `itsdangerous` (#2) already present.
