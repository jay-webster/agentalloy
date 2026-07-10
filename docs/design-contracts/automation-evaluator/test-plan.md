# automation-evaluator — Test Plan

## Test Cases

### Task 1 — store layer

- **T1.1 (AC1).** Open a `CandidateStore` against a fresh db, insert a
  candidate via `add()` (slice 1's method, pre-migration shape), then
  re-open the store (triggering `_ensure_columns` again) — original columns
  unchanged, `verdict`/`rationale`/`evaluated_at` present and `NULL`.
- **T1.2 (AC1).** Opening the store twice in a row does not raise (the
  "duplicate column" failure mode this task exists to avoid).
- **T1.3 (AC2).** `evaluate(id, "accept", "good fit")` then `list()` shows
  `status="evaluated"`, `verdict="accept"`, `rationale="good fit"`,
  `evaluated_at` set (non-`None`).
- **T1.4 (AC3).** `evaluate(id, "accept", ...)` then `evaluate(id, "reject",
  "actually no")` — exactly one row, reflecting the second call.
- **T1.5 (AC4).** `evaluate("does-not-exist", "accept", "x")` returns
  `False`, raises nothing.
- **T1.6 (AC5).** `evaluate(id, "maybe", "x")` raises `ValueError`
  mentioning the invalid value, before any row is touched (verify via a
  subsequent `list()` showing the row unchanged from before the bad call).

### Task 2 — CLI

- **T2.1 (AC2, AC6).** `ingest evaluate <id> --verdict accept --rationale
  "..."` then `ingest list --status evaluated` output includes the verdict
  and rationale text.
- **T2.2 (AC5).** `ingest evaluate <id> --verdict bogus --rationale "x"`
  exits non-zero via argparse's own `choices` validation, no traceback.
- **T2.3 (AC6, regression).** `ingest list --status new` output for an
  un-evaluated row is byte-identical in shape to slice 1's existing format
  (no verdict/rationale suffix) — proves the format-change in approach.md §5
  doesn't regress the already-shipped output.

### Task 4 — live proof

- **T4.1 (AC8).** Documented in the PR description / QA report: real
  `ingest evaluate` calls against slice 1's actual 31 ingested candidates,
  with `ingest list --status evaluated` output shown as evidence.
