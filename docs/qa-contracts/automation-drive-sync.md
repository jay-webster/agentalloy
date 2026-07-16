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

## Verdict (tasks 1-4, original transport)

Clean. 6 of 7 acceptance criteria verified by automated test plus a real
live-proof run against the production database; the 7th (export-format
consistency) is verified by direct inspection, which is the only method
available given the Apps Script half runs entirely outside any tool this
session has access to — that limitation is named explicitly, not hidden.

---

## REST-transport rework (tasks 59-61, 2026-07-15)

Reopened after the original MCP-tool-based transport (`create_file`)
turned out to have a payload-size ceiling that would break on a
realistic-size `candidates.db` — see `approach.md` §6 and the routine
doc's own Notes for the full history. Tasks 59-61 replace steps 1, 2, and
5 of the routine with a REST-direct, service-account-authenticated
transport. Documentation- and operations-only — no Python touched.

### Checks

- **Old-transport removal (task 59's AC)**: `grep -n
  "mcp__Google-Drive__" automation/routines/scheduled-drive-sync.md
  automation/docs/drive-sync-credential-setup.md` — the only two hits are
  both negative/historical prose (line 7: "this routine does **not** use
  a Google Drive MCP connector..."; a Notes entry describing the
  superseded transport). Zero actual call sites remain in steps 1, 2, or
  5 — all replaced with literal `curl` recipes.
- **Recipe completeness (task 59's AC)**: routine doc names, as literal
  shell, all four required recipes — JWT-bearer token exchange
  (`openssl dgst -sha256 -sign` + `curl -X POST .../token`), list/find
  (`GET .../files` with a `q` filter), download (`curl -o`, disk-to-disk),
  and resumable upload for both the overwrite (`PATCH`) and first-run
  create (`POST`) cases, each followed by `curl -T` streamed from disk.
  Matches `approach.md` §6's recipe line for line.
- **No tool-argument/tool-result payload path (task 59's AC)**: every
  download uses `curl -o <path>` and every upload uses `curl -T <path>`
  or `curl -T .automation/candidates.db "$LOCATION"` — bytes move
  disk-to-disk over HTTP, never through a tool-call argument or a
  tool-result payload. This is the literal fix for the ceiling that broke
  the old transport.
- **Scope check**: `git diff --stat main` shows exactly two files —
  `automation/routines/scheduled-drive-sync.md` (modified) and
  `automation/docs/drive-sync-credential-setup.md` (new). Zero diff to
  `src/agentalloy/`, `automation/store.py`, or `automation/cli.py`.
- **Secret-handling check**: `grep -rn "BEGIN PRIVATE KEY\|iam
  .gserviceaccount.com" automation/routines/scheduled-drive-sync.md
  automation/docs/drive-sync-credential-setup.md` — the one hit is the
  generic `<name>@<project>.iam.gserviceaccount.com` placeholder pattern,
  not a real value. No credential value has appeared in this repo, this
  session's transcript, or been typed into an interactive Claude session
  at any point — both docs and the live-proof run consistently describe a
  git-ignored `.env.local`, populated by Jay directly and only ever
  `source`d inside self-contained script executions.
- **Live proof (task 61, AC8 — real, against the real Shared Drive)**: a
  600,000-byte synthetic file (above the 536,576-byte floor) run through
  the full recipe end to end:
  - **T7.3 PASS** — `files.list` with `q="<folderId>" in parents`
    succeeded under the service account's `drive.file`-scoped token
    against the Shared Drive, which was shared with the account, not
    created by it — the exact live-unknown flagged in `approach.md` §6's
    verification note.
  - **T7.1 PASS** — resumable upload of the 600,000-byte file succeeded
    with no payload-size error (the `POST .../upload/...?uploadType=resumable`
    → `curl -T` sequence), returning a real file id.
  - **T7.2 PASS** — the uploaded file was re-downloaded and
    byte-diffed (`cmp -s`) against the original with zero mismatch.
  - Test file cleaned up afterward via `trashed: true` (reversible, not a
    hard delete). The Shared Drive's only other contents are the two
    well-known production files, untouched by this proof.
  - First live-proof attempt failed the upload with a genuine
    `403 storageQuotaExceeded` against a personal-My-Drive folder —
    a real, previously-undiscovered constraint (service accounts have
    zero My Drive storage quota), not a bug in the recipe. Resolved by
    moving to a Workspace Shared Drive (storage pooled at the drive
    level) and adding `supportsAllDrives=true`/
    `includeItemsFromAllDrives=true` to every list/download/upload call —
    documented inline in both docs' dated Notes rather than silently
    absorbed. Second run, against the Shared Drive, passed clean.

### Review

**Design conformance**: matches `approach.md` §6 on the JWT-bearer
recipe, the four REST call sites, and "full replacement, not a
size-threshold hybrid" — no old-transport code path retained anywhere.
**One real deviation from what §6 describes, not from what it intends**:
§6's provisioning steps still describe a personal My Drive folder shared
at Editor role; the live proof in task 61 found this doesn't work
(service accounts have zero My Drive quota) and both `automation/docs/
drive-sync-credential-setup.md` and the routine doc were updated to a
Workspace Shared Drive at Content Manager role instead. `approach.md`
itself was not updated to match — a **minor doc-staleness gap**, not a
functional one, since the two documents QA actually verifies here
(the credential-setup doc and the routine doc) are internally consistent,
correctly reflect the real provisioning path, and both name the pivot and
its reason inline. Worth a follow-up edit to `approach.md` §6 so the
design doc doesn't read as contradicting its own build artifacts, but
does not block shipping the artifacts that are actually correct.

**AC9 (access boundary verifiable by inspection)** — still met under the
new mechanism: Shared Drive membership (one non-owner principal, Content
Manager role) is exactly as inspectable as the originally-designed folder
share, just via the Shared Drive's own member list instead of a folder's
sharing dialog. Both docs state this explicitly.

### Findings

- **Critical**: none.
- **Nit**: `approach.md` §6 not updated to reflect the Shared Drive pivot
  (see Review, design conformance) — cosmetic, doesn't affect either
  artifact QA is verifying.
- **Nothing else to report**: the live-unknown §6 flagged for QA/build to
  actually confirm (`files.list` against a shared-not-created folder)
  came back positive on real infrastructure, not assumed.

## Verdict (tasks 59-61, REST-transport rework)

Clean. Both success criteria sets (task 59's transport-recipe
requirements, task 61's live-proof test cases T7.1/T7.2/T7.3) are met by
direct inspection plus a real end-to-end run against production Drive
infrastructure — not a mock or a dry run. The one deviation found
(Shared Drive instead of a personal-Drive folder) was a real, necessary
fix for a genuine platform constraint discovered live, is fully
documented in both artifacts, and preserves the original design's intent
(narrow scope, one inspectable share) rather than working around it.
Ready to route to ship.

## Overall verdict

**Clean, ready to ship.** All 7 tasks across both build passes (1-4:
import/routine/appsscript/live-proof; 59-61: REST-transport rework)
verified. The only open item is the pre-existing, explicitly-named gap
that the Apps Script export half cannot be live-proven from this session
(requires Jay's own Google OAuth consent) — unchanged by the transport
rework, since it never touched the export side.
