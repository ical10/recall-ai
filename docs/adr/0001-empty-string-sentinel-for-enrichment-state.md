# Empty-string sentinel for Vocab Item enrichment status

When a Vocab Item is created (via `POST /vocab` or the seed script) it has no LLM-generated definition yet, so we encode the "pending enrichment" state as `VocabItem.definition == ""` and "ready" as `definition != ""`. Considered an explicit `enrichment_status` enum column but rejected it: the sentinel reuses an existing NOT NULL Text column (no migration), keeps the contract between the seed/POST path and the Slice A content pipeline in a single string comparison, and only `/review` and `due_today` need to filter on it — both already join Vocab Item for other reasons.

If a third state is ever needed (e.g. `failed`, `manually_curated`), this approach breaks and we migrate to a proper column. Until then, the sentinel is load-bearing: `/review` and `/dashboard` filter `VocabItem.definition != ""` to hide pending cards; the Slice A worker uses the same filter to find rows that still need enrichment.
