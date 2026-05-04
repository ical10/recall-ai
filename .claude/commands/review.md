# Slash Command: /review

**Triggers:** The Reviewer agent on the current diff or named file/PR

## usage
```
/review
/review app/services/content.py
/review "the changes I just made to the enrichment pipeline"
```

## what claude does
1. Loads `dev/agents/reviewer.md` to adopt the Reviewer role
2. Reads the specified file, diff, or recent changes
3. Runs through the full review checklist (security → correctness → optimization → code quality → tests)
4. Returns a structured review report with verdict: Approve / Request Changes / Block

## install in Claude Code
Add to `.claude/commands/review.md` in your project root:

```markdown
---
description: Run a thorough security-first code review on the current changes
---

Read dev/agents/reviewer.md, adopt the Reviewer role, then review: $ARGUMENTS

If no argument is given, review all uncommitted changes (`git diff`).

Produce the full review report with verdict.
```

## example output
```
Verdict: Request Changes

Security findings:
- HIGH: Raw LLM output written to DB in services/content.py:87 before Pydantic validation

Correctness:
- Missing Mapped[] annotation on Word.difficulty_level column

Tests:
- WordEnrichment schema has no validation-failure test

Summary: One high-severity issue blocks merge. Two minor items can be fixed in the same PR.
```
