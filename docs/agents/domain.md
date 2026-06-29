# Domain Docs

How the engineering skills should consume this repo's domain documentation when exploring the codebase.

This is a **single-context** repo.

## Before exploring, read these

- **`CONTEXT.md`** at the repo root — the domain glossary.
- **`CLAUDE.md`** at the repo root — its "architecture decisions" section is where this project's ADRs
  currently live (inline, dated, with rationale). Treat each entry there as an ADR for the purposes of
  the conflict-flagging rule below.

If any of these files don't exist, **proceed silently**. Don't flag their absence; don't suggest
creating them upfront.

## Use the glossary's vocabulary

When your output names a domain concept (in an issue title, a refactor proposal, a hypothesis, a test
name), use the term as defined in `CONTEXT.md`. Don't drift to synonyms the glossary explicitly avoids.

If the concept you need isn't in the glossary yet, that's a signal — either you're inventing language
the project doesn't use (reconsider) or there's a real gap (note it).

## Flag ADR conflicts

If your output contradicts a decision in `CLAUDE.md`'s architecture-decisions section, surface it
explicitly rather than silently overriding:

> _Contradicts the "htmx over next.js" decision (May 2026) — but worth reopening because…_
