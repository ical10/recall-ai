# Plan: Railway preview branch CI/CD

## Goal
Add the minimum repo changes needed so Pull Requests can produce Railway preview environments cleanly, and document the remaining dashboard/secrets setup that cannot be truthfully encoded in git alone.

## Scope
- Add a dedicated GitHub Actions workflow for preview deploy orchestration
- Keep the existing CI workflow as the quality gate
- Add repo documentation for the required Railway project settings and GitHub secrets
- Merge the work back into `feat/web-og-icon-metadata` after pushing the implementation branch

## Constraints
- No new dependency unless already required by Railway’s current official flow
- Prefer Railway native PR environments over a custom branch-per-environment deploy system
- Avoid guessing project/service/environment IDs in committed config

## Expected files
- `.github/workflows/*`
- `README.md` and/or `CLAUDE.md`
- this plan file

## Implementation outline
1. Verify Railway’s current PR environment and CLI/token behavior from official docs.
2. Create a new branch from `feat/web-og-icon-metadata` for this work.
3. Add a workflow that runs on pull requests, waits for CI, and exposes the Railway preview contract using secrets/config that the repo can safely own.
4. Document the one-time Railway dashboard setup: enable PR environments, Railway-provided domains, and required secrets.
5. Validate the changed workflows locally as far as possible, then push the branch and merge it back into `feat/web-og-icon-metadata`.

## Validation
- YAML sanity check by reading the rendered workflow carefully
- `pnpm --filter @recall-ai/web test`
- `pnpm --filter @recall-ai/web build`
