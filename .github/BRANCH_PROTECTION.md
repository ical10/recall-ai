# Branch Protection: main

Run the command below once to lock `main` on GitHub. You must have admin rights on the repo.

```bash
gh api -X PUT /repos/ical10/recall-ai/branches/main/protection \
  --input - <<'EOF'
{
  "required_status_checks": {
    "strict": true,
    "contexts": [
      "Lint & Test",
      "Migration Check",
      "Secret Scan (Gitleaks)"
    ]
  },
  "enforce_admins": true,
  "required_pull_request_reviews": {
    "dismiss_stale_reviews": true,
    "require_code_owner_reviews": true,
    "required_approving_review_count": 0
  },
  "restrictions": null,
  "allow_force_pushes": false,
  "allow_deletions": false,
  "required_linear_history": true,
  "block_creations": false
}
EOF
```

## Setting explanations

| Setting | Value | Why |
|---|---|---|
| `required_status_checks.strict` | `true` | Branch must be up-to-date with `main` before merging — prevents stale-base merges that pass CI but conflict at merge time. |
| `contexts` | three job names | All three CI jobs must be green. Names must match the `name:` field in `ci.yml` exactly. |
| `enforce_admins` | `true` | Admin users cannot bypass protection. Solo project, but defence-in-depth. |
| `required_pull_request_reviews` | approving count = 0 | You are the sole developer. CodeRabbit comments are surfaced but a formal approval from a second human is not required. Set to 1 if you add collaborators. |
| `require_code_owner_reviews` | `true` | Ties to `.github/CODEOWNERS` — any PR automatically requests @ical10. |
| `dismiss_stale_reviews` | `true` | Pushing new commits to a PR dismisses previously approved reviews, forcing re-review of updates. |
| `allow_force_pushes` | `false` | Prevents history rewriting on `main`. |
| `allow_deletions` | `false` | Prevents accidental `git push origin :main`. |
| `required_linear_history` | `true` | Enforces squash-merge or fast-forward only — matches the project's squash+merge preference. |
| `restrictions` | `null` | No push restrictions beyond the status checks above (any collaborator can push a PR). |

## Verify protection is active

```bash
gh api /repos/ical10/recall-ai/branches/main/protection | python3 -c "
import sys, json
d = json.load(sys.stdin)
print('Status checks:', d['required_status_checks']['contexts'])
print('Force push allowed:', d.get('allow_force_pushes', {}).get('enabled'))
print('Admin enforced:', d['enforce_admins']['enabled'])
"
```

## Re-trigger a stuck CI run

If a PR's checks are stuck (e.g. after a flaky runner):

```bash
# Push an empty commit to re-trigger all checks
git commit --allow-empty -m "chore: retrigger CI"
git push

# Or re-run a specific workflow run by ID
gh run list --branch <your-branch> --limit 5
gh run rerun <run-id>
```
