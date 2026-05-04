# Slash Command: /session-end

**Triggers:** End-of-session memory write to the Obsidian vault

## usage
```
/session-end
```

Run this before closing Claude Code. It writes a session summary to the vault so the next session picks up with full context.

## what claude does
1. Reviews everything that happened in the current session (files changed, decisions made, issues hit)
2. Writes a session summary to `dev/sessions/YYYY-MM-DD.md`
3. Appends a one-liner to the "Recent Sessions" section of `dev/index.md`
4. Updates the "Open Issues / TODOs" section of `dev/index.md` with anything left unresolved
5. Flags any new architecture decisions that should be logged to `dev/decisions/`

## session summary format
Saved to `dev/sessions/YYYY-MM-DD.md`:

```markdown
# Session: YYYY-MM-DD

## What we did
- [bullet list of completed work]

## Decisions made
- [any architecture or design decisions taken]

## What's still open
- [unfinished tasks, blockers, next steps]

## Files changed
- [list of files touched]

## Notes
- [anything worth remembering that doesn't fit above]
```

## install in Claude Code
Add to `.claude/commands/session-end.md` in your project root:

```markdown
---
description: Write a session summary to the Obsidian vault and update the index
---

Review this entire session and:
1. Write a summary to dev/sessions/YYYY-MM-DD.md (use today's date)
2. Append a one-liner to the Recent Sessions section of dev/index.md
3. Update Open Issues in dev/index.md
4. Flag any decisions that should go in dev/decisions/

Use the format defined in dev/commands/session-end.md.
```
