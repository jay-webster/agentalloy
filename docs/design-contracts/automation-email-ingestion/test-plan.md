# automation-email-ingestion — Test Plan

## Test Cases

### Task 1 — store layer

- **T1.1 (AC1).** `add(candidate)` twice with the same `message_id` — second
  call returns `False`, `list()` still returns exactly one row.
- **T1.2 (AC2).** `add(candidate)` with no `status` given — the stored row's
  `status` is `"new"`.
- **T1.3 (AC3).** Seed rows with `status` in `{"new", "evaluated",
  "accepted"}`; `list(status="new")` returns only the `"new"` rows.
- **T1.4 (AC4, happy path).** `add` then `mark(message_id, "accepted")`
  returns `True`; a subsequent `list(status="accepted")` includes it.
- **T1.5 (AC4, missing id).** `mark("does-not-exist", "accepted")` returns
  `False`, raises nothing.

### Task 2 — config loader

- **T2.1 (AC5, happy path).** A fixture `sources.yaml` with 2 entries loads
  to a `SourceAllowlist` containing exactly those 2 entries.
- **T2.2 (AC5, missing file).** `load_sources(path=<nonexistent>)` raises
  `SourcesConfigMissing` whose message contains
  `"sources.example.yaml"`.
- **T2.3 (AC5, malformed).** A fixture YAML that isn't a list of strings
  (e.g. a nested mapping) raises with a message identifying the bad value,
  not a bare YAML parser traceback.

### Task 3 — CLI

- **T3.1.** `ingest add` with all required flags, run twice with the same
  message id — second invocation's output/exit code reflects "already
  present", store still has one row (CLI-level restatement of T1.1, proving
  the wiring, not just the store in isolation).
- **T3.2.** `ingest list --status new` output includes only rows with that
  status, formatted one line per row.
- **T3.3.** `ingest mark <id> accepted` on an id that doesn't exist prints a
  clear "not found" message and exits non-zero, not a traceback.

### Task 5/6 — scope + live proof

- **T5.1 (AC6, scope check).** `git diff --stat` for this feature's commits
  shows zero paths under `src/agentalloy/`.
- **T5.2 (AC7, determinism check).** `grep -rn "lm_client\|embed" automation/`
  (excluding the markdown routine) returns no matches.
- **T5.3 (AC8, live proof).** Documented in the PR description / QA report:
  actual `ingest list` output from a real run against Jay's inbox after
  reconnecting Gmail, or an explicit note if the configured allowlist
  matched zero messages that day.
