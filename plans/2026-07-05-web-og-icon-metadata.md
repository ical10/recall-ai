# Plan: OG image, icon, and metadata for `apps/web`

## Goal
Add branded social preview assets and baseline site metadata for the Vite web app, using the product positioning from `README.md` and the visual system in `apps/web/src/index.css`.

## Scope
- Update the static document metadata in `apps/web/index.html`
- Add a generated site icon asset
- Add a generated Open Graph image asset
- Add a small asset-generation script so the visuals are reproducible instead of hand-edited binaries
- Add a focused test for the metadata injected into the document head

## Constraints
- No new dependency unless existing tooling cannot generate the assets cleanly
- Keep the diff local to `apps/web` plus this plan file
- Preserve existing visual language: cream background, ink outlines, tangerine/teal/sky accents, Fraunces/DM Sans tone

## Expected files
- `apps/web/index.html`
- `apps/web/public/*` or equivalent static asset path
- `apps/web/scripts/*` or equivalent tiny generator script
- `apps/web/src/*test*` for a minimal verification

## Implementation outline
1. Inspect how Vite serves static assets in this app and use the existing path conventions.
2. Generate one icon and one OG image with simple SVG-first artwork derived from the current landing page look.
3. Wire the assets into `index.html` with title, description, theme color, canonical/basic social tags, and app icon links.
4. Add one small test that asserts the key metadata is present or that the root document title/description setup stays intact.
5. Run web tests and a production build.

## Validation
- `pnpm --filter @recall-ai/web test`
- `pnpm --filter @recall-ai/web build`
