# Plan — 1:1 UI Parity (HTMX/Jinja2 pages → React pages)

## Context

Phase 0 of the modernization (epic #37) replaces the HTMX/Jinja2 frontend with a React SPA, then
**purges the legacy UI once 1:1 parity is signed off** (#44). The legacy UI is not generic — it's a
bespoke "paper-flashcard" design system: a custom palette, three Google Fonts (Fraunces / DM Sans /
JetBrains Mono), hand-rolled CSS component classes (`btn-pop`, `card-paper`, `washi`, `marker`,
`chip`, `confetti-dot`), tilt/flip/pop/confetti/sparkle/wiggle animations, and washi-tape + dot-grid
decoration. Reaching "looks identical" by re-deriving this in React would be slow and lossy.

This plan makes parity **near-mechanical**: port the design system *once* (it's just CSS + config +
font links, framework-agnostic), then each React screen reuses the **exact same className strings**
copied from the templates — only `{{ jinja }}` → `{expr}` and `hx-*` swaps → local React state change.

It complements the backend/endpoint plan (saved at
`apps/api/plans/2026-06-28-phase-0-react-spa-migration.md`), which owns the `/api` JSON surface this
UI consumes. Scope here is **visual/interaction parity** of the screens.

Backend complete = pixel-identical screens + identical interactions, verified side-by-side, gating #44.

## Strategy: two layers — CSS contract (verbatim) + atomic components (own the composition)

Parity and modularity are not in tension if the two concerns are separated cleanly:

- **Layer 1 — the CSS design system stays as global classes, ported verbatim.** `.btn-pop`,
  `.card-paper`, `.washi`, `.marker`, `.chip`, `.confetti-dot`, the tilt/animation utilities, the body
  background — these *are* the visual contract. They keep their exact CSS so the pixels match. We do
  **not** re-derive the look in JS (no CVA re-implementation of the shadow/border/radius).
- **Layer 2 — React atoms own *applying* those classes, so the markup lives in one place.** The
  duplication risk isn't the CSS — it's pasting `className="btn-pop btn-pop--primary text-base"` plus a
  trailing-glyph span into 15 screens. Each repeating markup pattern becomes one atomic component
  (`<Button>`, `<Card>`, `<Washi>`, `<Chip>`, `<Marker>`, `<Eyebrow>`, `<IconBadge>`) that composes the
  Layer-1 classes from props. Screens compose atoms; **no screen repeats a class string a
  pattern already owns.**

So: copy each class string **once** into the atom that owns it, then express every screen as a
composition of atoms. *ponytail: atoms are justified strictly by repetition (the inventory below counts
call-sites); a one-off bit of markup stays inline rather than becoming a speculative component.*

## Step 1 — Port the shared design foundation (do this first, once)

Framework-agnostic; unblocks every screen. All target paths under the new `apps/web/` (see backend plan).

- **Tailwind config** — copy the `theme.extend` block (colors, fontFamily, boxShadow, backgroundImage,
  keyframes, animation) from `apps/api/tailwind.config.js` into `apps/web/tailwind.config.ts`
  **verbatim**; set `content` to `./index.html` + `./src/**/*.{ts,tsx}`.
- **Component/utility CSS** — copy the `@layer base / components / utilities` blocks from
  `apps/api/static/css/input.css` **verbatim** into `apps/web/src/index.css`: the body dot-grid +
  radial-gradient background, the `h1–h4` Fraunces rule, and every component class (`.btn-pop` + its
  `--primary/--ink/--teal/--berry/--honey/--sky/--ghost` variants, `.card-paper` / `--lg`, `.washi` +
  color variants, `.chip`, `.marker` + variants, `.confetti-dot`) and the utilities (`.tilt-l/-r/-2`,
  `.text-shadow-pop`, `.perspective-card`).
- **Fonts** — in `apps/web/index.html`, copy the three `<link>` tags verbatim: the two
  `fonts.googleapis.com` / `fonts.gstatic.com` preconnects and the `css2?family=Fraunces…&family=DM+Sans…&family=JetBrains+Mono…&display=swap` stylesheet. Also `<meta name="theme-color" content="#FFF8E7">`.
- **`<body>`** = `class="min-h-screen font-sans antialiased"` (matches `base.html`).
- **Drop**: the htmx CDN script tags and `json-enc` ext (not needed — React owns interaction).

*Self-check:* render one ported `card-paper--lg` + `btn-pop--primary` screen next to the HTMX one at
the same width; the offset shadow, border, radius, font, and background must match before proceeding.

## Step 2 — Atomic component inventory (driven by repeating patterns)

Mined from the template catalog by counting where each markup pattern recurs. Build the **atoms** (own
a Layer-1 class string + variant logic); **composites** are built from atoms; **deferred** ones are not
built until a real call-site exists. One tiny `cn()` (clsx) helper composes conditional classes (tilt,
animate, variant) — the only new "infra". Target dir `apps/web/src/components/ui/` (atoms) and
`components/` (composites).

### Atoms — build these (each appears across many screens)

| Atom | Owns (Layer-1 classes) | Props | Recurs in |
|---|---|---|---|
| **`Button`** | `btn-pop` + `--primary/ink/teal/berry/honey/sky/ghost`, size `text-sm/base`, optional `w-full`, optional trailing glyph span | `variant`, `size`, `as` (`button`\|`a`), `href`, `fullWidth`, `glyph`, `onClick` | landing, login, about, dashboard, review, settings, done, banners, add-word — **~everywhere** |
| **`RatingButton`** | `btn-pop btn-pop--{color} flex-col py-4` + emoji + label (the column variant; folds in the inline `.flex-col` style) | `quality` (0/2/4/5), `color`, `emoji`, `label` | review rating grid (×4); landing showcase mirrors the colors |
| **`Card`** | `card-paper` / `card-paper--lg`, `tilt-*`, `animate-*`, renders optional `<Washi>` + children | `size` (`sm`\|`lg`), `tilt`, `animate`, `washi?`, `className` | stat cards, review cards, forms, milestone, login, about, landing showcase, empty-states — **~everywhere** |
| **`Washi`** | `washi` + `--teal/berry/sky`, position passthrough | `color`, `className` (position/tilt) | every card with tape (10+ sites) |
| **`Chip`** | `chip` + colored dot span | `dotColor`, `children` | landing, review header, card prompt/reveal |
| **`Marker`** | `marker` / `--teal/berry` inline highlight | `color`, `children` | landing, dashboard, settings, about, done, add-word, milestone |
| **`Eyebrow`** | `font-mono text-[11px] uppercase tracking-[0.22em] text-ink-mute` | `children`, `className` (size) | nearly every screen/card header |
| **`IconBadge`** | `inline-flex items-center justify-center border-2 border-ink rounded-{lg/xl/2xl/3xl} bg-{color}` + child SVG/text | `size`, `shape`, `color`, `children` | stat-card icons, interval badge, vocab added/exists circles, done check, nav logo (8+ sites) |
| **`Icon`** | the recurring inline SVGs (`check`, `info`, `google`, stat `clock/check/flame`) as a small named set | `name`, `className` | check reused (added + done); google reused (login + about); stat icons (×3) |

### Composites — built *from* atoms (screen-specific, but still reused)

- **`Nav`** (`base.html` + `partials/nav.html`) — logo (`IconBadge` + honey dot), authed links, lavender
  avatar, Sign out / Sign in (`Button`). User from `useQuery(/api/me)`.
- **`GoogleSignInButton`** — `Button as="a" variant="ink" fullWidth href="/auth/login"` + `Icon name="google"`.
  Full-page redirect, **not** a fetch (auth stays the server OAuth flow). Login + about.
- **`StatCard`**, **`IntervalCard`** (replace the Jinja macros), **`AddWordCard`**, **`MilestoneBanner`**,
  **`ReviewCard`**, **`DoneCard`**, **`InterestsForm`** — each composes `Card` + `Button`/`Marker`/`Eyebrow`/`IconBadge`.
- **Decorations**: `FloatingShape` (login/about bordered shapes), `Blob` (review blur accents),
  `ConfettiBurst` (done row of `confetti-dot`s) — presentational, no logic.

### Deferred — do **not** build yet (YAGNI)

- **`Modal` / `Dialog`** — *no overlay exists in any parity screen* (the dashboard "spotlight" is an
  inline dismissible card, built from `Card` + `useState`, not a modal). Build a `Modal` atom only when
  the first real overlay appears (e.g. Phase 1 audio replay / a confirm dialog), so its API is shaped by
  a concrete need. Flagged here so it's a conscious deferral, not an oversight.
- **`DisplayHeading`** — display headings vary in size per screen (`text-5xl`→`text-8xl`); a wrapper buys
  little. Keep `font-display … font-black tracking-tight` inline per heading.

## Step 3 — Per-screen parity mapping

Each screen is a **composition of the Step-2 atoms** (not raw class strings), bound to its `/api`
endpoint (backend plan), with every `hx-*` swap translated into a local state transition. Representative
target paths under `apps/web/src/`. Build order: atoms (Step 2) → composites → routes.

| Screen | Source template(s) | Target | Data | Interaction translation |
|---|---|---|---|---|
| **Landing** | `pages/index.html` | `routes/index.tsx` | none (static) | hero + showcase `Card` + streak `Card` + 3 feature `Card`s; `Chip`, `Marker`, `Button`. Just links. |
| **Login** | `pages/login.html` | `routes/login.tsx` | none | `Card` + `GoogleSignInButton` + `FloatingShape`s; `Eyebrow`, `Marker`. |
| **About** | `pages/about.html` | `routes/about.tsx` | none | `Card` + `GoogleSignInButton` + `FloatingShape`s. |
| **Dashboard** | `pages/dashboard.html` + `partials/macros.html` (`stat_card`, `interval_card`) + `vocab-form` + `milestone-banner` | `routes/dashboard.tsx`, `components/StatCard.tsx`, `IntervalCard.tsx`, `AddWordCard.tsx`, `MilestoneBanner.tsx` | `GET /api/dashboard` (`UserStats`) | `stat_card`/`interval_card` macros → components (same conditional color thresholds: interval ≥7 teal / ≥3 sky / else honey). Spotlight dismiss = `useState`. Milestone "Open them" `POST /api/milestones/seen` → invalidate + `navigate('/review')`. Add-word form (below). |
| **Add-word flow** | `vocab-form` → `vocab-added` / `vocab-exists` | `AddWordCard.tsx` | `POST /api/vocab` | Three HTMX swap states → one component with `'form' \| 'added' \| 'exists'` state. Submit posts token; 200-new → added card (teal washi), 200-dup → exists card (berry washi); "Add another"/"Try a different word" → back to `'form'`. |
| **Review** | `pages/review.html` + `partials/card.html` (prompt) + `rating.html` (revealed) + `done.html` | `routes/review.tsx`, `components/ReviewCard.tsx`, `DoneCard.tsx` | `GET /api/review/batch` | The HTMX reveal/rate round-trips become the **Zustand review store** (backend plan #40/#41): `showing → revealed → next`. Prompt card (tilt-l-2, tangerine washi, `animate-pop-in`) → Reveal → revealed card (tilt-r, teal washi, `animate-flip-in`, definition + dashed example box) → 4 rating buttons (berry/honey/teal/sky, quality 0/2/4/5, emojis) `POST /api/review/ratings` → next card. Empty/end → `DoneCard` (confetti row, wiggle check, marker). **Keyboard: Space = reveal/flip** (template hints "space to flip"). |
| **Settings** | `pages/settings.html` + `partials/interests-form.html` | `routes/settings.tsx`, `components/InterestsForm.tsx` | `GET /api/settings`, `PUT /api/settings/interests` | Checkbox grid over `all_tags`, `has-[:checked]` styling kept verbatim; selected from user tags; underscore→space label. Submit → PUT → "Saved" badge (React state, replaces the HTMX form re-swap). |
| **Archive** | *(none — no HTMX page exists; `/vocab` is JSON-only)* | `routes/archive.tsx` | `GET /api/archive` | **Net-new UI, no parity target.** Build fresh from the same atoms (`Card`, `Chip`, `IntervalCard`-style rows) so it inherits the look for free. Plain paginated list (PRD defers virtualization). Flagged so it's not mistaken for a migration. |

### HTMX → React interaction translation (the recurring pattern)

| HTMX | URL | React equivalent |
|---|---|---|
| Reveal `hx-get` swap `outerHTML` | `/review/{id}/reveal` | store `reveal()` → render revealed card (no fetch; data already in batch) |
| Rate `hx-post` + `hx-vals quality` | `/review/{id}/rate` | store `rate(quality)` → `POST /api/review/ratings` → `next()` |
| Add form `hx-post` json-enc swap | `/vocab` | `mutation.mutate({token})` → set state `added`/`exists` |
| "Add another" `hx-get` swap | `/vocab/form` | set state `'form'` |
| Interests `hx-post` swap | `/settings/interests` | `PUT` mutation → set `saved=true` |
| Milestone `hx-post` swap none | `/milestones/seen` | mutation → invalidate `/api/dashboard` |

Routing maps the legacy URLs 1:1 (`/`, `/about`, `/dashboard`, `/review`, `/settings`, plus new
`/archive`) so muscle memory and links carry over.

## Verification — side-by-side parity sign-off (gates #44)

Both apps run together: legacy HTMX on uvicorn `:8000`, new SPA via Vite `:5173` (proxying the API).
Seed one account with: due cards, ≥1 completed review (for "recently reviewed" + streak), an unseen
milestone, and a duplicate-word case.

1. **Visual** — with the browser MCP (`claude-in-chrome`), open each legacy screen and its React
   counterpart at the **same viewport width** (check both `sm`/`md` breakpoints used in the markup),
   screenshot both, and compare: fonts, palette, offset shadows, tilts, washi placement, spacing,
   the dot-grid + radial background. Walk the per-screen checklist: landing, login, about, dashboard
   (incl. milestone banner + empty-state + spotlight), review **prompt → revealed → done**, settings.
2. **Interaction** — in the SPA: reveal flips with `animate-flip-in`; Space flips; the 4 ratings
   advance and persist (confirm via `/api/dashboard` totals/streak moving); add a new word → "added"
   card, re-add same word → "exists" card; toggle interests → "Saved"; milestone "Open them" clears
   the banner and routes to review; done screen shows after the last card.
3. **Responsive** — narrow to mobile width; nav collapses (`hidden … sm:inline`), grids reflow
   (`sm:grid-cols-3`, `lg:grid-cols-5`) identically to legacy.
4. `pnpm lint` + `pnpm test` green (a smoke test per atom renders each variant; route smoke tests
   render from a mocked client; the review store's state machine is unit-tested per the backend plan).
5. **Modularity check** — `grep -r "btn-pop\|card-paper\|\bwashi\b\|\bchip\b\|\bmarker\b" apps/web/src`
   returns hits **only inside `components/ui/` atoms**, not in route/composite files. A pattern's class
   string living in two places is the signal to extract another atom. Atoms reference Layer-1 classes;
   screens reference atoms.

*Manual side-by-side is the parity method.* Automated visual-regression (Playwright snapshot diffs)
is **deferred** — add only if parity regressions recur after the legacy purge. *ponytail: a whole
screenshot-diff harness + CI wiring to compare against a UI we're about to delete is throwaway work.*

## Scope notes

- **Parity targets = 6 screens** with existing HTMX UI (landing, login, about, dashboard, review,
  settings). **Archive is net-new** — same look, no before/after to match.
- **Login/landing/about** are ported (the #44 purge deletes their templates too), but they're static
  and low-risk — do them quickly alongside the auth-flow wiring.
- **Auth is unchanged**: sign-in is a full-page redirect to `/auth/login`; the SPA never fetches it.
- This plan owns *markup + styling + interaction*. The endpoints (`/api/dashboard`, `/api/review/*`,
  `/api/settings`, `/api/archive`, `/api/vocab`, `/api/me`), the Zustand store internals, and tests
  live in the backend plan (`apps/api/plans/2026-06-28-phase-0-react-spa-migration.md`).
- Per project rules: lint + full suite pass before commit; component additions ship a smoke test.
