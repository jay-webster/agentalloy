# automation-drive-sync — QA Report

## Checks

- **New tests**: 6 added to `test_cli.py` — all well-formed lines land
  (T1.1), injection-guard inheritance via imported data (T1.2), malformed
  JSON mid-file doesn't block the rest (T1.3), missing required field
  skipped (T1.4), re-import of the same file is safe (T1.5), summary
  counts are exactly accurate for a mixed fixture (T1.6). All of slices
  1-4's existing 42 tests still pass unmodified. **48 total in
  `tests/automation/`.**
- **Lint**: `uv run ruff check automation/ tests/automation/` — clean.
  `uv run ruff format --check` — clean.
- **Type checker**: `uv run pyright automation/` — **0 errors**, 9
  warnings (7 new, all `reportUnknownArgumentType` on values pulled from
  `json.loads`'s untyped `dict` — same category this repo already
  downgrades to warning for `yaml.safe_load` in `config.py`; not a new
  kind of gap). `.gs` files are outside pyright's Python-only scope by
  construction, nothing to typecheck there.
- **Scope check (AC5)**: `git status --short` shows only `automation/cli.py`
  (modified), `automation/routines/scheduled-drive-sync.md` (new),
  `automation/appsscript/` (new), and `tests/automation/test_cli.py`
  (modified). Zero paths under `src/agentalloy/`.
- **Determinism check (AC5)**: `grep -rn "lm_client\|embed" automation/cli.py
  automation/appsscript/newsletter-export.gs` — zero hits. `import-jsonl`
  uses only stdlib `json`; no new dependency added.
- **Field-list inspection (AC6)**: `_IMPORT_REQUIRED_FIELDS` in `cli.py`
  (`message_id, thread_id, source, subject, received_at, snippet`) and
  the `row` object constructed in `newsletter-export.gs` — same six
  field names, same order documented in both files, no extras, no
  omissions. This is the seam between the tested and untested halves; it
  cannot be verified by a runtime test (see spec Assumptions), only by this
  inspection.
- **Live proof (AC7)**: hand-built a 3-line JSONL fixture shaped like real
  Apps Script output (realistic sender/subject/snippet, one line with a
  subject engineered to trip the injection guard) and ran it through the
  real `uv run python -m automation.cli ingest import-jsonl` command
  against the actual production database (not a scratch one) in this
  session. All 3 rows landed correctly; the flagged row showed
  `[FLAGGED: ignore-previous-instructions]` in `ingest list` output,
  confirming the guard fires on imported data exactly as it does on
  directly-`add()`ed data, with zero new guard code. Test rows deleted
  afterward; production db confirmed back to 31 real candidates.

## Review

### Acceptance criteria (against `docs/spec-contracts/automation-drive-sync.spec.md`)

1. **`import-jsonl` adds every well-formed line via the existing `add()`
   path — MET.** `test_import_jsonl_all_wellformed_lines_land`,
   `test_import_jsonl_inherits_injection_guard` (store-level proof the
   guard applies without new code), plus the live proof.
2. **Malformed line is skipped, not fatal — MET.**
   `test_import_jsonl_malformed_line_is_skipped_not_fatal` (bad JSON),
   `test_import_jsonl_missing_required_field_is_skipped` (valid JSON,
   missing field) — both non-fatal, both exit 0.
3. **Re-importing the same file is safe — MET.**
   `test_import_jsonl_reimport_same_file_is_safe` — proves the importer
   doesn't generate a synthetic id per call; it reuses the JSONL's own
   `message_id`, so `add()`'s existing idempotency applies unchanged.
4. **Summary output is accurate — MET.**
   `test_import_jsonl_summary_counts_are_accurate` — a fixture with one
   already-present, two new, and one malformed line produces exactly
   "2 added, 1 already present, 1 skipped."
5. **No product code touched, no new dependency, no LLM call — MET.**
   Scope and determinism checks above.
6. **Export format specified and consistent — MET, by inspection (the
   only verification method available for this AC, per spec).** See
   Checks.
7. **Live proof of the testable half — MET.** See Checks — real command,
   real production database, realistic fixture data including an
   adversarial line, cleaned up after.

### Non-goals respected

Checked against the spec's Out of Scope: no `RemoteTrigger` routine was
created or enabled (that's a follow-up action, with explicit go-ahead, once
Jay has deployed the Apps Script); the Apps Script was not deployed by this
session (Jay's own account, his own consent — the README is explicit about
this); no reconciliation between a human's local db and a routine's
Drive-hosted copy was attempted; no export-file cleanup/truncation logic
was added; no Discord wiring; `evaluate-candidate.md` itself is
unmodified — the drive-sync routine references it, doesn't duplicate or
change it.

### Design conformance

Matches `approach.md` on every decision: line-by-line parsing (not a
whole-file JSON load, which the malformed-line tests specifically require);
no new `CandidateStore` method (the injection-guard-inheritance test
proves this was the right call — free correctness from reusing `add()`);
fixed, hardcoded Drive filenames in both the routine doc and the Apps
Script (verified identical by direct comparison); no `--dry-run` flag
added (not required by any AC, and `add()`'s idempotency makes a real run
just as safe to inspect afterward).

### Findings

- **Required**: none.
- **Critical**: none.
- **Nit**: the Apps Script half (`newsletter-export.gs`) is verified by
  code review and field-list inspection only, not a live run — an
  explicit, unavoidable gap named in the spec's Assumptions (no tool here
  can execute Apps Script or grant Jay's Google OAuth consent on his
  behalf), not an avoidable one being glossed over. Once Jay deploys it,
  a genuine live end-to-end proof (Gmail → Apps Script → Drive → routine
  import) becomes possible and is worth doing as a follow-up, not part of
  this slice's QA bar.
- **Dead code**: none.

## Verdict

Clean. 6 of 7 acceptance criteria verified by automated test plus a real
live-proof run against the production database; the 7th (export-format
consistency) is verified by direct inspection, which is the only method
available given the Apps Script half runs entirely outside any tool this
session has access to — that limitation is named explicitly, not hidden.
Ready to route to ship.
