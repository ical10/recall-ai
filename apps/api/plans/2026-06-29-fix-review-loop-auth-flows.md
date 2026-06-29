# Plan — Fix broken review/auth flows (daily review boundary, about sign-in, logout/front page)

## Context

Bugs found exercising the current HTMX app on the `phase-0-react-spa-migration` branch (this
worktree). The app is mid-migration to a React SPA + JSON API, so **we don't invest in the dying Jinja
UI** — templates, `nav.html`, and legacy `reviews.py` HTMX endpoints are deleted at the #44 purge.

**Decision (from earlier):** a minimal stopgap in the live app for the user-blocking review flow so
people can finish a day's review before React ships; the cosmetic about/logout bugs are fixed
correctly in the React build, not patched in Jinja. All are recorded as React acceptance criteria so
none get ported forward.

---

## Bug 1 — Review has no daily boundary (the headline bug)

**Symptoms:**
- Reviewed all 12 cards today, all "Good", yet `/review` still serves cards.
- Earlier: AGAIN-rated cards re-appear within a session (the `again_queue`).

**Diagnosis.** Two compounding causes:
1. **No "done for today" concept.** `_next_due_review` (`app/api/reviews.py:28-42`) serves any card
   with `due_at <= now` (or `due_at IS NULL`) and never excludes cards already reviewed today. Every
   enrolled card is created **due immediately** — starters (`auth.py:122`, `due_at=now`) *and* every
   nightly shared-pool / personalized enrollment (`workers/content_gen.py:244`, `due_at=now`). So a
   user's "due now" set is 12 starters **plus** all accumulated pool cards, with no daily cap and no
   terminal "no more today" state. SM-2 *does* push rated cards to ≥tomorrow, so they leave the queue —
   the queue just has more cards than the user expects, and never announces a daily end.
2. **In-session `again_queue`** (`reviews.py:24-25,45-71,175-186`) re-serves AGAIN cards after 10
   minutes even though their `due_at` is tomorrow.

**Target behavior.** "Today's review set" = cards **due by end of the user's local day** that have
**not been reviewed yet today**. Review serves from that set; when it's empty, show a terminal
**"No more cards to review today"** screen. AGAIN reschedules to tomorrow (no in-session re-show).
This also makes `/review` agree with the dashboard's `due_today` count (`services/stats.py`), which
already uses end-of-today + the user's timezone.

**Reuse:** mirror the due-today predicate from `compute_user_stats` (`services/stats.py:77-88`:
`suspended is False`, `due_at < end_of_today_local`, `definition != ""`, user-tz aware). Factor it into
one shared helper so review and dashboard can't drift.

---

## Part A — Stopgap in the live HTMX app (Bug 1 only)

Smallest change that gives a correct daily boundary; thrown away at #44.

- **`app/api/reviews.py`:** replace `_next_due_review`'s filter with the **due-today + not-reviewed-today**
  predicate (end-of-today local, user tz, `last_reviewed_at < start_of_today_local OR NULL`). Delete
  `AGAIN_QUEUE_KEY` / `AGAIN_REQUEUE_MINUTES` / `_pick_next_review` and the session-queue reads/writes
  in `review_page` and `review_rate`; both just call the due-today query and render the done partial on
  empty. Mark `# ponytail: stopgap, removed when the React review flow lands (#40/#41)`.
- **`templates/partials/done.html`:** copy tweak to "No more cards to review today" (one-line, throwaway).
- **Tests** (`apps/api/tests/api/test_reviews*.py`, write first / watch fail): rate all 12 starters GOOD
  → `/review` shows the daily-done screen and serves nothing more **today**; a card reviewed today does
  not re-appear today; an AGAIN card does not re-appear this session. Drop stale `again_queue` tests.

*Not patched in Jinja: Bugs 2 & 3 (cosmetic) — fixed in Part B.*

**Out of scope (note, don't build):** a hard per-day *new-card cap* (e.g. only N new pool cards/day).
Today every enrolled card is due immediately; if "12 starters + a large pool in one day" is too much,
that's a new-card-scheduling feature — flag for product, don't fold in here. *ponytail: the user asked
for a daily-done boundary, not a throttle; ship the boundary.*

---

## Part B — Correct behavior in the React build (folded into Phase 0)

Acceptance criteria of the rebuild — no `OptionalUserDep`, no Jinja.

- **Bug 1 → daily batch + terminating store (#40).** `GET /api/review/batch` (`build_daily_batch`)
  returns exactly today's set (**due by end of local day, not reviewed today**, reusing the shared
  predicate); no server `again_queue`. The Zustand store iterates the batch and ends on empty with a
  **"No more cards to review today"** done screen (the `DoneCard`). AGAIN reschedules `due_at`
  server-side. **Acceptance:** store unit test — exhausted batch → done, no re-show; backend test —
  batch excludes already-reviewed-today cards.
- **Bug 2 → about CTA gated client-side.** React `about` route hides the Google button + bottom
  sign-in CTA when authenticated, via the `useQuery('/api/me')` the nav already uses (`if (!user)`).
- **Bug 3 → logout + real front page.** JSON logout endpoint clears the session; SPA routes to the
  React `/login`; `/` is the React landing for anon, redirect to `/dashboard` when signed in. Replaces
  the `/`→`/dashboard`→401 Jinja bounce.

---

## Files

**Part A (now):** `app/api/reviews.py` (due-today predicate + delete `again_queue`),
`app/services/stats.py` or a small shared module (extract the due-today predicate for reuse),
`templates/partials/done.html` (copy), `apps/api/tests/api/test_reviews*.py`. No `deps.py` / `about.py`
/ `auth.py` / `about.html` changes.

**Part B (during Phase 0):** React `about` / `login` / landing routes, Zustand review store + tests,
`build_daily_batch` (uses the shared due-today predicate), `/api/me`, JSON logout — owned by the
SPA-scaffold (#38), review (#40/#41), and parity plans.

## Verification

**Part A (now):**
1. `uv run pytest apps/api/tests/api/test_reviews.py` then `pnpm test` + `pnpm lint` — green; new
   daily-boundary tests pass.
2. `pnpm dev`: review every due card today (incl. one AGAIN) → "No more cards to review today"; reload
   `/review` → same screen; dashboard `due_today` matches the number actually served.

**Part B (when those React screens exist):**
3. Store test: exhausted batch → done, no re-show; batch excludes reviewed-today cards.
4. `/about` signed-in → no sign-in CTA; signed-out → CTA present.
5. Logout → sign-in page; `/` signed-out → landing, signed-in → `/dashboard`.

## Notes

- Implement Part A on this **`phase-0-react-spa-migration`** worktree; removed by #44 with the rest of
  legacy `reviews.py`.
- Dropped from earlier drafts: `OptionalUserDep` + `about.html` gating — patches to soon-deleted Jinja.
- Carry-forward: the shared **due-today (not-reviewed-today)** predicate is the contract both
  `build_daily_batch` and the dashboard must use, so `/review` and `due_today` always agree.
