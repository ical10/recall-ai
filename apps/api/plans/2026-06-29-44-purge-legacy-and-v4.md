# Plan — Expand PR #51: finish parity, purge legacy Jinja/HTMX (#44), Tailwind v4 everywhere

## Context

PR #51 (Phase 0: React SPA + JSON API) is green. The goal now is to land **#44 (legacy HTMX/Jinja2
purge) in this same PR** so the root Tailwind v3 build can be removed and the repo goes **Tailwind v4
everywhere** (the v3 CLI is the only v4 blocker, and it's coupled to the Jinja UI — see below).

**The blocker for v4** is solely the legacy Jinja CSS pipeline (root `build:css*` scripts → v3 CLI +
JS config + `@tailwind`/`theme()` in `input.css`). Jinja `base.html` requires that `output.css`, so
the CSS build and the Jinja UI are coupled — removing the v3 blocker *requires* removing the Jinja UI.

**But the React app is not at parity yet**, so we must close the gaps before deleting Jinja:
- `__root.tsx` is a bare `<Outlet/>` — **no nav** (no way to move between screens, no logout)
- **no `login`, `about`, or `landing` routes**
- **no add-word UI** (Jinja `vocab-form`), **no logout control**
- **FastAPI doesn't serve the SPA** (`main.py` has no dist mount / catch-all; SPA only runs on Vite in dev)

Outcome: SPA reaches functional parity, FastAPI serves it, all Jinja/HTMX is gone, root Tailwind is
removed (React owns v4), tests rewritten, all gates green.

## Constraints (from CLAUDE.md)
- **Auth/user-data code is hand-written + human-reviewed** — steps touching the session/login flow
  (B2, C2) are flagged HITL; I implement a candidate, you review before merge.
- lint + full test suite green before each commit; conventional commits; atomic commits.

## Phase A — Close parity (additive, no deletion, low risk)

A1. **App shell / nav** — rebuild `partials/nav.html` as a React layout in `__root.tsx`: logo, links
   (Deck `/dashboard`, Review `/review`, Settings `/settings`, About `/about`), user name + avatar,
   Sign out. Auth state from a new `GET /api/me` (below). Unauth shows Sign in → `/auth/login`.
A2. **`GET /api/me`** (`app/api/json/`) → `{id, name, email, avatar_url}` or 401. Feeds the nav.
A3. **Login route** `/login` — port `pages/login.html` (marketing card + Google button → full-page
   `/auth/login`). Static.
A4. **About route** `/about` — port `pages/about.html`; gate the sign-in CTA on `useQuery('/api/me')`.
A5. **Landing route** `/` for anon — port `pages/index.html` (hero + features); authed `/` → `/dashboard`.
A6. **Add-word UI** on the dashboard — port `vocab-form` → `vocab-added`/`vocab-exists` state machine,
   `POST /api/vocab` (endpoint already exists; confirm JSON contract).
A7. Component smoke tests for each new route; `tsc` + vitest green.

## Phase B — Serve the SPA from FastAPI

B1. `main.py`: after routers, mount `apps/web/dist` static + SPA catch-all to `index.html`, excluding
   `/api`, `/auth`, `/static`, `/healthz`. Build SPA in the web railpack step (`pnpm --filter web build`).
B2. **[HITL auth]** 401 handler: non-`/api` unauth → redirect to the SPA `/login` (not the deleted
   Jinja `/auth/login-page`); `/api/*` stays JSON 401.

## Phase C — Purge legacy (destructive — only after A+B verified)

C1. Delete `apps/api/templates/**`; delete Jinja routes/handlers: `about.py`, the `TemplateResponse`
   paths in `dashboard.py`, the HTMX flow in `reviews.py` (`/review`, `/reveal`, `/rate`),
   `settings.py` form posts, `vocab.py` HTMX partials. Remove `templates` from `deps.py`. Remove
   `jinja2` (+ any htmx asset refs) from deps.
C2. **[HITL auth]** Remove/redirect `/auth/login-page`; keep `/auth/login` + `/auth/callback`
   (→ `/dashboard`) + `/auth/logout` (→ `/login`). Hand-written, audited before merge.
C3. **Drop root Tailwind entirely** (this is the v4 "everywhere" payoff): delete root `build:css*` /
   `watch:css` scripts, `apps/api/static/css/input.css`, `apps/api/tailwind.config.js`, the gitignored
   `output.css`, and the root `tailwindcss` dep. React owns Tailwind v4 in `apps/web`. Supersedes the
   pending v3-revert dep change (root tailwind is removed, not pinned).
C4. Rewrite/delete Jinja-coupled tests: `test_reviews.py`, `test_dashboard.py`, `test_about.py`,
   Jinja parts of `test_settings.py`/`test_vocab.py`, `test_root.py`, `test_static.py` (if static CSS
   only). Keep/extend the `json/` endpoint tests, services tests, and (adjusted) `test_auth.py`.

## Phase D — Verify end-to-end

- `pnpm lint`, API `pnpm test`, web `vitest` + `tsc -b` + `vite build` all green.
- `grep -r TemplateResponse apps/api/app` and `grep -ri jinja2` return nothing live.
- Run the served SPA (FastAPI serving dist): login → dashboard (add a word) → review → rate (persists)
  → settings → archive → logout → lands on `/login`. Landing `/` shows for anon.
- CI green on the PR (branch protection).

## Commit sequence (atomic, on `phase-0-react-spa-migration`)
1. feat(web): app shell/nav + `/api/me`
2. feat(web): login, about, landing routes + add-word UI
3. feat(api+web): FastAPI serves the SPA build  *(B2 auth bit flagged for review)*
4. refactor(api): purge Jinja/HTMX templates, routes, deps  *(C2 auth bit flagged for review)*
5. chore(build): remove root Tailwind v3 pipeline (React owns v4)
6. test: replace Jinja-coupled tests with SPA/API coverage

## Risks / notes
- Biggest risk is auth (B2, C2) and losing the deployable HTMX fallback — mitigated by doing A+B
  (parity + serving) and verifying before any C deletion.
- This supersedes the in-flight dependency-update commit: root `tailwindcss` ends up **removed**, so
  the v3-vs-v4 root question dissolves. The apps/web major bumps (Vite 8, Vitest 4, TS 6, etc.) stay;
  TS 6 has an `openapi-typescript` peer warning — pin TS to latest 5.x unless we accept the warning.
