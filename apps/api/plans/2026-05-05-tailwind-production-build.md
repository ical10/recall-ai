# Tailwind Production Build Pipeline Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the Tailwind Play CDN `<script>` in `base.html` with a real, version-pinned Tailwind 3.x compile pipeline that produces `apps/api/static/css/output.css`. Dev runs `tailwindcss --watch` alongside uvicorn; prod compiles once during the Nixpacks build phase. Compiled output is gitignored.

**Architecture:** Tailwind CLI (the standalone JS-based one, installed via pnpm) reads `apps/api/static/css/input.css` plus `apps/api/tailwind.config.js` (which scans `apps/api/templates/**/*.html`) and emits `apps/api/static/css/output.css`. The base template references `/static/css/output.css`. Same file path serves dev and prod — no env branching, no Jinja conditionals. Dev gets fresh rebuilds via `tailwindcss --watch`; prod builds once before the uvicorn process starts.

**Tech Stack:** Tailwind CSS 3.4+, `concurrently` for parallel pnpm scripts (or `pnpm run --parallel`), Nixpacks build phase update.

---

## File Structure

**Create:**
- `apps/api/tailwind.config.js` — Tailwind 3 config scanning `templates/**/*.html`
- `apps/api/static/css/input.css` — Tailwind directives only (`@tailwind base; @tailwind components; @tailwind utilities;`)

**Modify:**
- `package.json` (root) — add `tailwindcss` and `concurrently` devDeps; add `build:css`, `watch:css` scripts; rewrite `dev` to run uvicorn + tailwind watch in parallel
- `apps/api/templates/base.html` — replace `<script src="https://cdn.tailwindcss.com">` with `<link rel="stylesheet" href="/static/css/output.css">`
- `apps/api/tests/test_root.py` — update HTML body assertion (the substring `tailwindcss` no longer appears in the rendered page; replace with `output.css` substring)
- `nixpacks.toml` — add a Node + pnpm install + `pnpm run build:css` build phase before the Python phase
- `.gitignore` — add `apps/api/static/css/output.css`

**No edits to:** any Python source under `apps/api/app/`, the FastAPI routes, the Settings class.

---

## Task 1: Add Tailwind devDeps + scripts

- [ ] **Step 1**: Edit `package.json` (root) — add to `devDependencies`:

```json
"devDependencies": {
  "concurrently": "^9.0.0",
  "tailwindcss": "^3.4.0",
  "turbo": "^2.0.0"
}
```

(Keep existing `turbo` entry; just add `concurrently` and `tailwindcss`.)

- [ ] **Step 2**: Add to `scripts` (replace `dev`, add `build:css` and `watch:css`):

```json
"scripts": {
  "dev": "concurrently -n 'css,api' -c 'cyan,green' 'pnpm watch:css' 'uv run uvicorn app.main:app --app-dir apps/api --reload --port 8000'",
  "build:css": "tailwindcss -c apps/api/tailwind.config.js -i apps/api/static/css/input.css -o apps/api/static/css/output.css --minify",
  "watch:css": "tailwindcss -c apps/api/tailwind.config.js -i apps/api/static/css/input.css -o apps/api/static/css/output.css --watch",
  "start": "uv run uvicorn app.main:app --app-dir apps/api --host 0.0.0.0 --port ${PORT:-8000}",
  "worker": "uv run --project . celery -A app.core.celery_app:celery_app --workdir apps/api worker --loglevel=info",
  "beat": "uv run --project . celery -A app.core.celery_app:celery_app --workdir apps/api beat --loglevel=info",
  "test": "uv run pytest -v",
  "lint": "uv run ruff check apps/api && uv run ruff format --check apps/api && uv run mypy apps/api/app"
}
```

The `start` script does NOT include `build:css` because Nixpacks runs `build:css` as a separate build phase (Task 5) before the `start` command runs.

- [ ] **Step 3**: `pnpm install` — verifies the new deps resolve. Run from repo root.

- [ ] **Step 4**: Commit — `chore: add tailwindcss + concurrently dev dependencies and css scripts`.

---

## Task 2: Tailwind config + input

- [ ] **Step 1**: Create `apps/api/tailwind.config.js`:

```js
const path = require('path')

/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [path.join(__dirname, 'templates/**/*.html')],
  theme: {
    extend: {},
  },
  plugins: [],
}
```

The content glob uses `path.join(__dirname, 'templates/**/*.html')` so it resolves
relative to the config file's directory regardless of where `tailwindcss` is invoked
from. (Tailwind 3.4's default glob resolution is CWD-relative — using `__dirname`
makes the config robust against being run from any directory, e.g. by Nixpacks or
an IDE task runner.)

- [ ] **Step 2**: Create `apps/api/static/css/input.css`:

```css
@tailwind base;
@tailwind components;
@tailwind utilities;
```

- [ ] **Step 3**: Run `pnpm build:css` from the repo root. Confirm `apps/api/static/css/output.css` is created and contains utility classes (should be a few KB after JIT minification scans the index template).

  ```bash
  pnpm build:css && ls -la apps/api/static/css/output.css && grep -q "min-h-screen" apps/api/static/css/output.css && echo "OK: utility classes present"
  ```

- [ ] **Step 4**: Commit — `feat: add Tailwind 3 config and input.css entrypoint` (do NOT stage `output.css`; the next task gitignores it).

---

## Task 3: Gitignore the compiled CSS

- [ ] **Step 1**: Append to `.gitignore`:

```
# Tailwind compiled output
apps/api/static/css/output.css
```

- [ ] **Step 2**: Verify `git status` shows `output.css` as ignored (running `git check-ignore -v apps/api/static/css/output.css` should report a match).

- [ ] **Step 3**: Commit — `chore: gitignore Tailwind-compiled output.css`.

---

## Task 4: Switch base.html to compiled CSS + update tests (TDD)

- [ ] **Step 1**: Update `apps/api/tests/test_root.py` first to drive the change. Replace its content with:

```python
def test_index_renders_with_htmx_and_compiled_tailwind(client):
    response = client.get("/")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")

    body = response.text
    assert "RecallAI" in body
    assert "htmx.org" in body
    assert "/static/css/output.css" in body
    # Play CDN script must be gone
    assert "cdn.tailwindcss.com" not in body
```

- [ ] **Step 2**: Run the test — must fail (current `base.html` still has the CDN `<script>`).

  ```bash
  uv run pytest apps/api/tests/test_root.py -v
  ```

- [ ] **Step 3**: Edit `apps/api/templates/base.html` — replace:

  ```html
      <script src="https://cdn.tailwindcss.com"></script>
  ```

  with:

  ```html
      <link rel="stylesheet" href="/static/css/output.css" />
  ```

  Final `<head>` should look like:

  ```html
      <meta charset="utf-8" />
      <meta name="viewport" content="width=device-width, initial-scale=1" />
      <title>{% block title %}RecallAI{% endblock %}</title>
      <script src="https://unpkg.com/htmx.org@2.0.4"></script>
      <link rel="stylesheet" href="/static/css/output.css" />
  ```

- [ ] **Step 4**: Run the test again — must pass. (`output.css` exists from Task 2; FastAPI's StaticFiles mount serves it.)

- [ ] **Step 5**: Run the full suite — confirm everything else still passes.

- [ ] **Step 6**: Commit — `feat: serve compiled Tailwind CSS instead of Play CDN script`.

---

## Task 5: Update Nixpacks to compile CSS during build

- [ ] **Step 1**: Replace `nixpacks.toml` with:

```toml
[phases.setup]
nixPkgs = ["python311", "uv", "nodejs_22", "pnpm"]

[phases.install]
cmds = [
  "pnpm install --frozen-lockfile",
  "uv sync --frozen --no-dev",
]

[phases.build]
cmds = ["pnpm run build:css"]

[start]
cmd = "uv run uvicorn app.main:app --app-dir apps/api --host 0.0.0.0 --port $PORT"
```

Notes:
- `nixPkgs` adds `nodejs_22` and `pnpm` so Tailwind can compile during build.
- The build phase only runs for the **web** Railway service (worker/beat services use the same image but their start commands don't depend on `output.css`).

- [ ] **Step 2**: Smoke-test the full pipeline locally:

```bash
rm apps/api/static/css/output.css 2>/dev/null
pnpm build:css
ls -la apps/api/static/css/output.css   # must exist
pnpm test                                # 10+ passing
pnpm start &                             # background, must stay running
SERVER_PID=$!
sleep 3
curl -sI http://localhost:8000/static/css/output.css | head -3   # 200 OK
curl -s http://localhost:8000/ | grep -E "output\.css|cdn\.tailwindcss" || true
kill $SERVER_PID 2>/dev/null
```

Expected: `output.css` returns 200; index HTML contains `output.css` and not `cdn.tailwindcss`.

- [ ] **Step 3**: Commit — `chore: add Node + pnpm + Tailwind build phase to Nixpacks`.

---

## Task 6: Verify dev experience

- [ ] **Step 1**: Make sure `pnpm dev` starts both processes (uvicorn + tailwind watch) and that editing a class in `index.html` triggers a watch rebuild within ~1 second:

```bash
cp .env.example .env
pnpm dev &
PNPM_PID=$!
sleep 5
# Add a temp class to verify rebuild
echo "(touch templates to trigger watcher; then revert)"
# manual sanity — user verifies in their own session
kill $PNPM_PID 2>/dev/null
rm .env
```

This task has no code change — it's a smoke check that the parallel `concurrently` setup works. If the watcher and uvicorn both start cleanly and serve the page, you're done.

- [ ] **Step 2**: No commit — verification only.

---

## Out of Scope

- Tailwind plugins (`@tailwindcss/forms`, `@tailwindcss/typography`) — add when a real form or prose page needs them
- Custom theme tokens / brand colors — add with the design pass on the first real UI screens
- PostCSS pipeline beyond what `tailwindcss` runs internally
- Cache-busting hashed filenames (e.g., `output.<hash>.css`) — premature; defer until we see staleness in production
- Source maps — add if debugging compiled CSS becomes painful

## Risks

- **Watch mode + reload mode interplay** — uvicorn `--reload` watches Python files; Tailwind `--watch` watches templates. Editing a template fires both. Should be benign (template change + CSS rebuild are independent), but monitor for races on the first dev day.
- **`pnpm install --frozen-lockfile` requires `pnpm-lock.yaml` to be committed and current**. After Task 1 changes `package.json`, regenerate the lockfile (`pnpm install` does this) and stage it in the same commit. The Nixpacks build will fail if the lockfile drifts.
- **Railway worker and beat services share the build image** — ~~they'll waste a few seconds compiling CSS they don't use. Acceptable; the alternative (per-service `nixpacks.toml`) is more complex than the win.~~ **Resolved (2026-05-07):** added `nixpacks.worker.toml` and `nixpacks.beat.toml`; activate per service with `NIXPACKS_CONFIG_FILE`. See `apps/api/plans/2026-05-07-railway-worker-beat-deploy.md`.
- **Removing the Play CDN means dev now requires `pnpm build:css` to have run at least once** before `pnpm dev` actually displays a styled page (the watch script also runs an initial build, so this is automatic — but if someone runs `pnpm start` before `pnpm build:css`, they'll see unstyled HTML). Documented behavior; matches CLAUDE.md `## run / deploy`.
