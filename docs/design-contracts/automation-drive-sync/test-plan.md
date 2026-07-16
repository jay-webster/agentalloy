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

### Task 7 — transport fix at realistic size (AC8)

- **T7.1 (AC8).** Generate a local file ≥536,576 bytes (a real
  `candidates.db` after a batch, or a synthetic file of equal/greater
  size — the AC only requires the size floor, not that it literally be a
  sqlite file). Run the full token-exchange + resumable-upload recipe from
  approach.md §6 against the real Drive connector, live, in this session.
  Confirm success (HTTP 200/status from the final `PUT`, no payload-size
  error) — this is the case that would have failed under the original
  `create_file` approach and must now pass.
- **T7.2 (AC8).** Round-trip integrity: download the file just uploaded
  (via the same REST GET recipe) and diff its bytes against the original
  — proving the resumable upload didn't truncate or corrupt the transfer,
  not just that the HTTP call returned success.
- **T7.3 (AC8, verification note from approach.md §6).** Confirm
  `files.list` with `q='<folderId>' in parents` succeeds under the
  service account's `drive.file`-scoped token when the folder was shared
  with it (not created by it) — the one live-unknown flagged in design,
  not assumed safe by reasoning alone.

### Task 6 — credential scope inspection (AC9)

- **T9.1 (AC9).** Inspect the `agentalloy-automation/` folder's sharing
  settings in Drive: confirm exactly one non-owner principal (the service
  account's email) has access, with Editor role, and no other file or
  folder in Drive is shared with that same service account. Recorded as an
  inspection result (same style as T3.1), since this is a Drive-ACL fact
  to look at, not something a unit test asserts.
- **T9.2 (AC9).** Confirm the provisioning doc (Task 6) documents the
  token's scope (`drive.file`) and the exact folder-share step as the
  credential's complete access boundary — no broader scope requested or
  implied anywhere in the JWT claims or provisioning steps.
