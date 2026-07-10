# automation-drive-sync — Test Plan

## Test Cases

### Task 1 — `import-jsonl`

- **T1.1 (AC1).** A 3-line JSONL fixture (all well-formed, distinct
  `message_id`s) → all 3 land in the store with correct fields.
- **T1.2 (AC1, injection guard inheritance).** A JSONL line whose
  `subject` trips the injection-guard pattern → the imported row's
  `flagged`/`flag_reasons` are set exactly as they would be via a direct
  `store.add()` call — proving the guard applies without new code.
- **T1.3 (AC2).** A 3-line file where the middle line is invalid JSON →
  the first and third lines are imported, the summary reports 1 skipped,
  the command does not raise.
- **T1.4 (AC2).** A line that's valid JSON but missing a required field
  (e.g. no `subject`) → skipped with a warning, same non-fatal handling as
  T1.3.
- **T1.5 (AC3).** Running `import-jsonl` twice on the identical file →
  second run's `added` count is 0, store still has exactly the first run's
  rows (no duplication, no synthetic-id drift).
- **T1.6 (AC4).** A fixture with one already-present duplicate (import the
  same file twice, or seed one row via `add()` first, then import a file
  containing that `message_id` plus two new ones) → summary counts
  (added=2, already_present=1, skipped=0) match reality exactly.

### Task 4 — live proof

- **T4.1 (AC7).** A hand-built JSONL fixture (3-4 realistic entries, one
  injection-guard-tripping) imported via the real CLI (`uv run python -m
  automation.cli ingest import-jsonl <path>`) against a scratch store;
  `ingest list` output shown, including the flagged row's `[FLAGGED: ...]`
  prefix.

### Task 3 — field-list inspection (AC6)

- **T3.1.** Manually cross-check `newsletter-export.gs`'s JSON object
  construction against `import-jsonl`'s required-field list — same six
  field names, no extras required, no omissions. Recorded in the QA report
  as an inspection result, not a runtime test (per the spec's Assumptions —
  this is the seam that can't be tested end-to-end here).
