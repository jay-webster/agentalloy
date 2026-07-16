# newsletter-pipeline-efficiency — QA Report

## Checks

- `uv run ruff check automation/cli.py automation/store.py
  tests/automation/test_cli.py tests/automation/test_store.py` — pass, no
  issues.
- `uv run ruff format --check` (same files) — 1 file (`store.py`) needed
  reformatting (blank-line spacing around the new dataclass/method);
  applied `ruff format` and reverified — pass.
- `uv run pyright automation/cli.py automation/store.py` — 0 errors, 7
  warnings, all `reportUnknownArgumentType` on JSON-decoded dict values
  passed into `Candidate(...)`/`.append(...)` in the new
  `_cmd_evaluate_batch` — same shape and same pre-existing pattern as the
  untouched `_cmd_import_jsonl`, not a new class of warning.
- `uv run pytest tests/automation/ -q` — 99 passed (includes the 4 new
  tests: 3 in `test_store.py`, 1 in `test_cli.py`).
- `uv run pytest -m "not integration and not container and not
  harness_e2e"` (full CI-equivalent suite) — 4189 passed, 2 skipped, 14
  failed. All 14 failures are pre-existing and unrelated:
  `tests/test_simple_setup.py::TestContainerFlow::*`, failing on this
  machine because `podman` isn't on `PATH` (a local container-runtime gap,
  not a regression from this change — same failure set documented in
  earlier QA passes on this repo).

## Review

**Scope match.** `git diff --stat` touches exactly the 6 files scoped:
`automation/store.py`, `automation/cli.py`,
`automation/routines/scan-newsletters.md`,
`automation/routines/evaluate-candidate.md`,
`tests/automation/test_store.py`, `tests/automation/test_cli.py`. Nothing
under `src/agentalloy/**` or `automation/routines/scheduled-drive-sync.md`
changed.

**Correctness against the design's success criteria:**
- `evaluate_batch()` loops over the existing `evaluate()` method per row
  and does not reimplement the `FlaggedCandidateError` guard or the
  verdict/rationale UPDATE — the single source of truth stays `evaluate()`.
  Covered by `test_single_evaluate_unchanged_by_batch_addition` (proves the
  single-candidate path's flagged-guard behavior is byte-for-byte
  unchanged) and by `evaluate_batch()`'s own code, which contains no SQL
  and no verdict logic of its own.
- A flagged row in a mixed batch is refused (status/verdict left
  untouched) while the other rows in the same batch still commit —
  `test_evaluate_batch_mixed_accept_reject_flagged` asserts `.refused`
  contains only the flagged id, `.evaluated` contains the other two, and
  the flagged row's `status`/`verdict` remain `"new"`/`None` after the
  call.
- A `message_id` with no matching row lands in `.not_found` without
  aborting the rest of the batch — `test_evaluate_batch_not_found_does_not_abort_rest`
  asserts the valid row after it still gets evaluated.
- `ingest evaluate-batch` skips one malformed JSONL line and still
  processes the well-formed ones, reporting counts on stdout and
  refused/not-found ids on stderr —
  `test_evaluate_batch_malformed_line_is_skipped_not_fatal` asserts exit
  code 0, `"evaluated 1"` / `"skipped 1 malformed"` in stdout, and the
  well-formed row actually committed. `_cmd_evaluate_batch`'s parsing loop
  is structurally identical to `_cmd_import_jsonl`'s (same
  strip-blank/`json.JSONDecodeError`/required-fields-check/skip pattern),
  so the two commands' malformed-input behavior stays consistent.
- `scan-newsletters.md` step 2's query template gained `newer_than:35d`
  with a one-line rationale (missed-scan-day tolerance); no other step
  changed — confirmed by reading the file, this is documentation-only with
  no code path to unit-test.
- `evaluate-candidate.md` restructures steps 1, 2, 4, 5 around the 40-cap,
  fetch-the-whole-batch-first, single-combined-judgment-pass, and
  one-`evaluate-batch`-call shape. The four-lens criteria and decision
  rules inside step 4, and the step-3 treat-as-data warning, are unchanged
  text — confirmed by reading the file; nothing in the security-relevant
  injection-guard language was touched.

**Design constraints honored:** no schema change in `store.py` (no new
column, no migration); `BatchEvaluationResult` is a plain dataclass with no
behavior of its own; `evaluate_batch()`'s only control flow is
try/except-per-row around the existing `evaluate()` call, matching the
design's explicit "thin loop" framing.

## Verdict

**Pass.** No changes required. All success criteria verified by real test
coverage plus direct inspection of the two documentation-only routine
edits; scope confirmed exactly matching the 6 files named in the design.
