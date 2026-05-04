# Slash Command: /plan

**Triggers:** The Architect agent to produce a plan document before any multi-file work begins

## usage
```
/plan add google oauth login flow
/plan refactor the content selection service to support topic filtering
/plan add a new pydantic schema for translation enrichment
```

## what claude does
1. Loads `dev/agents/architect.md` to adopt the Architect role
2. Asks clarifying questions if the requirement is ambiguous
3. Produces a plan document with: summary, scope, files affected, dependencies, migration needed, implementation steps, open questions, risks
4. Saves the plan to `/plans/YYYY-MM-DD-[slug].md` in the project
5. Waits for developer approval before any code is written

## install in Claude Code
Add to `.claude/commands/plan.md` in your project root:

```markdown
---
description: Write an implementation plan before starting any multi-file task
---

Read dev/agents/architect.md, adopt the Architect role, then produce a plan for: $ARGUMENTS

Save the plan to /plans/ with today's date prefix and a short slug.
Do not write any code until the developer approves the plan.
```

## when it fires automatically
Per CLAUDE.md rules, any task that touches more than 3 files or requires a new dependency must go through `/plan` first — Claude should suggest this proactively if it detects scope creep.
