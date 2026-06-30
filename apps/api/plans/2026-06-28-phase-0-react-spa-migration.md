# Phase 0 Execution Plan — Recall-AI Modernization (HTMX → React SPA + JSON API)

## Context

The PRD (`Recall_AI_Extension_PRD.md`, GitHub epic #37) splits the work into **Phase 0 — Migration**
(HTMX/Jinja2 → React 19 SPA + JSON API) and **Phase 1 — Voice-First Chrome Extension**. The PRD has
already been broken into 13 GitHub issues (#37 epic; #38–44 Phase 0; #45–49 Phase 1).

This plan covers **all of Phase 0 (#38–44)** in execution detail. Phase 1 issues are listed only as
downstream consumers so the Phase 0 contracts (`/api` surface, generated TS types, `DailyBatch`,
idempotent ratings) are built right the first time.

**Why now:** the backend is API-less (everything returns `TemplateResponse`), so no non-HTML client —
including the extension — can consume it. Phase 0 produces an API-first backend and a React SPA at 1:1
parity, *then* purges the legacy UI. The risk is a big-bang rewrite on a solo project, so the legacy
HTMX app stays deployable until parity is signed off (#44 is gated on that).

## Current state & reuse map (verified)

- **Routes** mount at **root, no `/api` prefix** (`app/api/router.py`). Dashboard/review/settings return
  `TemplateResponse`; `vocab.py` already returns some JSON. New JSON endpoints go under a **new `/api`
  router mounted alongside** the legacy routes — legacy stays untouched until #44.
- **Reuse, do not rewrite:**
  - `app/services/stats.py::compute_user_stats(session, user) -> UserStats` — dashboard JSON is a thin wrapper.
  - `app/services/sm2.py::compute_next_review(state: ReviewState, quality: ReviewQuality) -> ReviewUpdate` — the curve contract; ratings endpoint calls it unchanged.
  - `app/api/deps.py`: `SessionDep`, `UserDep` (`get_current_user`, 401 if no session).
  - `UserStats`, `RecentRating`, `VocabRead`, `VocabListResponse`, `ReviewState`, `ReviewUpdate` schemas already exist (`app/schemas/`).
- **Models** (`app/models/`): `Review` (per-user SM-2 state, `suspended` flag, `due_at`), shared `VocabItem`
  (`audio_url` single nullable field today), `User`. Archive = paginated `Review`+`VocabItem` join filtered by user.
- **Auth**: `SessionMiddleware` signed cookie `recallai_session` (4h, `same_site=lax`, `https_only` env-driven).
  SPA is **same-origin** (FastAPI serves the built SPA) → the existing cookie works unchanged, no CORS, no token.
- **`again_queue`** (today in `request.session`) moves into the **Zustand** client store.
- **No frontend tooling exists**; `packages/shared/` is an empty `.gitkeep`; Tailwind 3.4 already configured
  (`apps/api/tailwind.config.js`) with the design tokens.

## Cross-cutting decisions (pinned)

1. **SPA lives at `apps/web/`** (new pnpm workspace; `apps/*` glob already covers it). Vite + React 19 + TS,
   Tanstack Router + Query, Zustand, Tailwind. *ponytail: one new app package, not a separate repo.*
2. **FastAPI serves the built SPA (single origin).** Prod: web build compiles `apps/web` → `apps/web/dist`,
   FastAPI mounts it with an SPA catch-all to `index.html`. Keeps **one** Railway web service, the session
   cookie same-origin, and **zero CORS**. The cross-origin token path is a Phase-1 extension concern (#47), not Phase 0.
3. **Dev**: Vite dev server (`:5173`) proxies `/api`, `/auth`, `/static` → uvicorn `:8000`. `pnpm dev` runs both.
4. **Type-gen = `openapi-typescript`** over FastAPI's `/openapi.json` → `apps/web/src/api/schema.d.ts`,
   checked in, verified by `tsc`. Zero extra Python dep. Requires every new endpoint to declare `response_model`.
   Add root script `gen:types`.
5. **`/api` 401 returns JSON, not a redirect.** Extend the existing 401 handler in `main.py`: if
   `path.startswith("/api")` → `JSONResponse(401)`; else keep the current HTMX/browser redirect. SPA redirects to login client-side.
6. **Tailwind**: keep the existing CLI build for the legacy app during parity; the SPA consumes Tailwind via
   its own Vite/PostCSS pipeline using the **same `tailwind.config.js` tokens**. Collapse to one pipeline at #44.

## Dependency DAG (and the two broken links to fix)

```
#38 scaffold ──┬──> #40 review-read ──> #41 review-write
               ├──> #42 settings
               ├──> #43 archive
               └──> #39 decoupled deploy (HITL)
#40 ──> #45 audio render (Phase 1)
#44 purge  ← BLOCKED-BY #40,#41,#42,#43 (+#39)   ← issue body shows "# —" (empty); fix it
#48 ext review ← BLOCKED-BY #45,#47               ← issue body shows "# —" (empty); fix it
```

**Action (pre-execution, non-code):** edit issue **#44** "Blocked by" → #40, #41, #42, #43 (parity complete),
and issue **#48** "Blocked by" → #45, #47. `gh issue edit 44 --body ...` / `gh issue edit 48 --body ...`.

**Build order:** #38 → (#40 → #41) ‖ #42 ‖ #43 → parity sign-off → #44. #39 runs after #38, before/with #44.

---

## #38 — SPA scaffold + dashboard tracer bullet  *(unblocks everything)*

Stand up `apps/web` and prove the full stack with the dashboard (read-only, reuses `compute_user_stats`).

**Backend**
- New `app/api/json/__init__.py` aggregating JSON routers under prefix `/api`; include it in `app/api/router.py`.
- `app/api/json/dashboard.py`: `GET /api/dashboard` → `response_model=UserStats`, body: `return await compute_user_stats(session, user)`. Uses `UserDep`, `SessionDep`.
- `main.py`: extend 401 handler for `/api` JSON (decision #5). Add SPA static mount + catch-all **last** (after routers), guarded so `/api`, `/auth`, `/static`, `/healthz` are never swallowed — but **only wire the catch-all in #39/once dist exists**; for #38 dev runs through the Vite proxy.
- Mark `apps/web/dist` gitignored.

**Frontend (`apps/web`)**
- `package.json` (Vite, react@19, react-dom@19, @tanstack/react-router, @tanstack/react-query, zustand, tailwindcss, typescript, openapi-typescript). `vite.config.ts` with dev proxy (decision #3). `tsconfig.json`. `index.html`. Tailwind/PostCSS using existing tokens.
- `src/api/client.ts`: centralized Tanstack Query client + a typed `fetch` wrapper keyed off `schema.d.ts`. **All CRUD goes through here** (PRD: one centralized client).
- `src/api/schema.d.ts`: generated by `openapi-typescript`.
- `src/routes/dashboard.tsx`: Tanstack Router route, `useQuery` → `/api/dashboard`, renders stats (due_today, streak, recent, milestone banner).
- `src/store/` placeholder for the review store (built in #40).

**Tooling (root)**
- `package.json` scripts: `gen:types` (`openapi-typescript http://localhost:8000/openapi.json -o apps/web/src/api/schema.d.ts`), `dev` runs uvicorn + vite, `build` builds SPA. `turbo.json`: add `web#build` outputs `dist/**`.

**Tests / DoD**
- Backend: `test_api_dashboard.py` — authed `GET /api/dashboard` returns `UserStats` shape; 401 unauth returns JSON.
- Frontend: smoke that the dashboard route renders from a mocked client (no heavy framework).
- `tsc` passes against generated types; `pnpm lint` + `pnpm test` green.

---

## #40 — Review read path (`DailyBatch` + Zustand state machine)

**Backend**
- `app/schemas/review.py` (extend) or `app/schemas/batch.py`: `DailyBatch` (denormalized) = list of cards, each
  `{review_id, vocab_item_id, token, definition, example_sentence, ease_factor, interval_days, repetitions, due_at, word_audio_url: str|None, example_audio_url: str|None}`. **Audio URL fields nullable, `None` in Phase 0** — populated by #45, which adds the model columns. *(Today's model has a single `audio_url`; do not split columns here — schema fields are forward-declared, mapped in #45.)*
- `app/services/daily_batch.py::build_daily_batch(session, user) -> DailyBatch`: due `Review`s (mirror the `due_today` filter in `stats.py`: `suspended is False`, `due_at < end_of_today_local`, `definition != ""`) joined to `VocabItem`. Single query, denormalized.
- `app/api/json/review.py`: `GET /api/review/batch` → `response_model=DailyBatch`.
- Schema tests: `DailyBatch` happy-path + validation-failure (per project rule).
- Service test: seeded user → batch contains exactly the due cards, correct shape.

**Frontend**
- `src/store/reviewSession.ts` (Zustand): state machine `idle → showing → revealed → next`, holds the batch +
  cursor in memory. **Illegal transitions rejected** (e.g. `reveal` from `idle`). Replaces the server `again_queue`.
- `src/routes/review.tsx`: `useQuery` → `/api/review/batch`, drives the store; show card → reveal → next. No rating yet.
- Store unit test (no DOM): full `show→reveal→next` cycle advances; illegal transitions rejected.

---

## #41 — Review write path (idempotent ratings)

**Backend**
- Schemas: `RatingIn {rating_id: UUID, card_id: UUID (review_id), grade: ReviewQuality, rated_at: datetime}`,
  `RatingsBody {ratings: list[RatingIn]}`, `SyncResult {applied: int, skipped: int}`. Each ships happy-path + validation-failure tests.
- **Idempotency store**: new `applied_rating` table (migration) keyed on `rating_id` (PK/unique). `apply_ratings`
  inserts-or-ignores per `rating_id`; a re-seen id is a no-op. *ponytail: a dedup table, not event-sourcing.*
- `app/services/rating_sync.py::apply_ratings(session, user, ratings) -> SyncResult`: for each unseen `rating_id`,
  load `Review`, `compute_next_review(ReviewState(...), grade)` (**reuse SM-2 unchanged**), persist new state +
  `last_reviewed_at`/`due_at`, record `rating_id`. Order ratings by `rated_at` so out-of-order input reconciles deterministically.
- `app/api/json/review.py`: `POST /api/review/ratings` → `response_model=SyncResult`.
- **Headline test**: applying the same `rating_id` twice == once (identical curve). Plus out-of-order reconciliation test.
- Keep the milestone-at-multiples-of-30 enqueue behavior from legacy `reviews.py` (non-blocking, no 500 on enqueue failure).

**Frontend**
- Wire Easy/Good/Hard (click + keypress) → store `rate` → `POST /api/review/ratings` (single-rating list on web;
  the extension batches offline). Optimistic advance to next card. Full `show→reveal→rate→next` cycle works.

---

## #42 — Settings screen in React

**Backend** — `app/api/json/settings.py`: `GET /api/settings` → `response_model` (user's `interest_tags` + the
`TOPIC_TAGS` catalog); `PUT /api/settings/interests` body `{tags: list[str]}` validated via existing `is_valid_tag()`,
returns the updated settings model. Reuse the validation in legacy `settings.py`. Schemas ship happy/failure tests.

**Frontend** — `src/routes/settings.tsx`: reads + writes interest tags through the API client; Tanstack Query
invalidates on save.

---

## #43 — Archive screen in React (plain paginated list)

**Backend** — `app/api/json/archive.py`: `GET /api/archive?page=&page_size=` → paginated `VocabRead`-shaped page of
the user's `Review`+`VocabItem` (mirror the existing `GET /vocab` `VocabListResponse` pagination). Reuse `VocabListResponse`. Schemas ship happy/failure tests.

**Frontend** — `src/routes/archive.tsx`: plain paginated list, **no virtualization** (PRD defers `react-window`
until a single user crosses ~1k cards). Smooth scroll at hundreds of cards.

---

## #39 — Decoupled Railway build/deploy  *(HITL — confirm hosting shape before applying)*

- `railpack.json` web build: after `pnpm install` + `uv sync`, run `pnpm --filter web build` (→ `apps/web/dist`)
  **and** keep `build:css:prod` until #44 collapses pipelines. Start cmd unchanged (uvicorn). `/healthz` intact.
- `main.py`: mount `apps/web/dist` as static + SPA catch-all (decision #2), excluding `/api`, `/auth`, `/static`, `/healthz`.
- `railway.json` preDeploy `alembic upgrade head` **unchanged** (web only). Worker/beat railpack+railway configs **untouched**.
- Verify on Railway: SPA assets serve, API reachable, healthcheck green, migrations ran.

---

## #44 — Purge legacy HTMX/Jinja2  *(only after parity sign-off; fix blocked-by to #40–43,#39)*

- Delete `apps/api/templates/**`, all `TemplateResponse` usages and legacy Jinja2 routes (`dashboard.py`,
  `reviews.py` HTMX paths, `settings.py` form posts, `about.py`, vocab HTMX partials). Keep `/auth/*` (OAuth redirect
  flow) and `/healthz`.
- Remove `jinja2` (and any `htmx` asset refs) from deps. Collapse Tailwind to the SPA's pipeline; drop the standalone
  `build:css` steps and `static/css/input.css` if now unused.
- Simplify the 401 handler (no more `hx-request` branch; `/api` JSON 401 + SPA redirect remain).
- App fully functional as a React SPA; `pnpm lint` + `pnpm test` green; no dead routes/templates.

---

## Verification (end-to-end)

1. `pnpm dev` → Vite `:5173` proxying uvicorn `:8000`. Log in via Google (full-page `/auth/login`), land on the SPA dashboard.
2. Dashboard renders real `compute_user_stats` data; `/api/dashboard` returns `UserStats` JSON; unauth `/api/*` → 401 JSON.
3. Review: load `/api/review/batch`, flip show→reveal, rate Easy/Good/Hard → `POST /api/review/ratings` → next.
   Confirm SM-2 curve updates in Postgres; **POST the same `rating_id` twice → identical curve** (idempotency).
4. Settings: toggle interests, reload, persisted. Archive: paginate hundreds of cards, smooth scroll.
5. `pnpm --filter web build` + `tsc` (types match live `/openapi.json`); `pnpm lint`; `pnpm test` (incl. new
   `daily_batch`, `rating_sync` idempotency, schema, Zustand-store tests).
6. After #44: `grep -r TemplateResponse apps/api/app` and `grep -ri jinja2 .` return nothing live; app still passes (1)–(5).

## Open items / HITL

- **#39 and #47 are HITL.** #39 is a deploy decision (confirm single-service-serves-SPA shape on Railway). #47 (Phase 1)
  is auth code — hand-written and manually audited per project rule; not AFK-agent merged.
- **Audio columns** (`word_audio_url`, `example_audio_url`) are added in **#45** (Phase 1) via migration; Phase 0
  forward-declares them as nullable `None` in `DailyBatch`. One alembic migration per logical change.
- **Extension session token** (#47): the SPA uses the same-origin cookie, but the cross-origin extension needs a
  bearer-token exchange the cookie can't cover — design that in #47, not Phase 0.
- Per project rules: new Pydantic schemas each need a happy-path + a validation-failure test; never store raw LLM
  output without schema validation; no commit without `ruff` + full suite passing.
