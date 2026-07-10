# automation-drive-sync — Tasks

## Tasks

1. **`automation/cli.py` — `ingest import-jsonl <path>`.** Per approach.md
   §1: line-by-line parse, per-line validation, `store.add()` per valid
   line, counted summary of added/already-present/skipped. No dependency
   on other tasks. Satisfies AC1, AC2, AC3, AC4, AC5.

2. **`automation/routines/scheduled-drive-sync.md`.** Per approach.md §2-3:
   the literal download → import → evaluate → upload sequence, naming the
   two well-known Drive filenames and the exact CLI invocation from Task 1.
   Depends on Task 1 (references its real command). No code, no tests of
   its own — verified by Task 4's live proof of the testable half plus
   AC6's field-list inspection.

3. **`automation/appsscript/newsletter-export.gs` + setup doc.** Per
   approach.md §4: the Gmail-search-and-export script, label-based dedup,
   and a companion doc walking Jay through deployment. No dependency on
   other tasks (this is the untestable-here half named in the spec's
   Assumptions) but must match Task 1's exact field names — this is what
   AC6 checks.

4. **Live proof of the testable half.** A hand-constructed JSONL fixture
   shaped like real Apps Script output (including one line that trips the
   injection guard, per AC1) imported via the real CLI in this session;
   `ingest list` output shown as evidence. Depends on Task 1.
