---
name: "source-command-init-codebase"
description: "Scan an existing codebase and generate a AGENTS.md from what you find"
---

# source-command-init-codebase

Use this skill when the user asks to run the migrated source command `init-codebase`.

## Command Template

You are being run on an existing project that does not yet have a AGENTS.md, or has one that needs to be regenerated from scratch.

Do the following in order:

1. **Scan the codebase** — read these to understand the project:
   - Root directory listing
   - package.json / pyproject.toml / Cargo.toml / go.mod (whichever exist)
   - Any existing README.md
   - Folder structure (2 levels deep)
   - Any existing linting/formatting config (ruff.toml, .eslintrc, prettier.config.js, etc.)
   - Any existing test config (pytest.ini, vitest.config.ts, jest.config.js, etc.)
   - Any existing CI config (.github/workflows/)
   - Any migration files (alembic, prisma, drizzle)

2. **Identify** from what you read:
   - Project name and domain (what does this thing do?)
   - Tech stack (languages, frameworks, databases, deployment)
   - Folder structure pattern
   - Conventions already in use (naming, test location, commit style)
   - Any architecture decisions that are visible in the code
   - What is currently being worked on (recent commits, open TODOs)

3. **Generate a AGENTS.md** using this exact structure:

```
# AGENTS.md

## project
- name: [detected]
- stack: [detected]
- deployed on: [detected or "unknown"]
- folder structure: [describe what you found]
- domain: [one sentence]
- solo/team: [infer from git log or leave as "unknown"]

## conventions
[list what you actually found — naming patterns, test location, commit style, etc.]
[mark anything you inferred vs. anything explicitly configured]

## architecture decisions
[only include decisions that are visible in the code — don't invent]
[format: "chose X over Y (date if visible): reason"]

## current focus
[infer from recent git commits, open TODOs, or WIP files — be honest if unclear]

## rules
- never commit without running [detected lint command] and [detected test command] first
[add any other rules you can infer from the codebase config]
```

4. **Write the file** to AGENTS.md in the project root.

5. **Report back** with:
   - What you found vs. what you had to infer
   - Anything that needs the developer to fill in manually (mark these with `# TODO:`)
   - Whether the pre-commit hook's lint/test commands match what you found

Do not invent conventions, stack choices, or decisions that aren't visible in the code. Mark uncertain items with a comment.
