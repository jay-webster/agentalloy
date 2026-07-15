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

5. **`automation/routines/scheduled-drive-sync.md` — replace steps
   1/2/6 with the REST-direct transport.** Per approach.md §6: rewrite the
   three Drive-touching steps as literal `curl` recipes (JWT-bearer token
   exchange once at the top of the routine, then list/download for steps
   1-2, resumable PATCH+PUT for the renamed step 5) instead of
   `mcp__Google-Drive__download_file_content` /
   `mcp__Google-Drive__create_file` calls. Depends on Task 2 (edits the
   same file). Satisfies AC8, AC9.

6. **Provisioning doc for the service-account credential.** A short
   companion doc (or a new section in the routine doc itself) walking
   through: creating the Cloud project/service account/key, creating and
   sharing the `agentalloy-automation/` folder, and which two fields
   (`client_email`, `private_key`) go into routine-only env config — same
   documentation bar `automation-discord-relay.md` sets for its own
   credential. No dependency on other tasks; this is documentation, not
   code. Satisfies AC9.

7. **Live proof of the transport fix at realistic size.** Using the real
   Drive connector available in this session (not the `RemoteTrigger`
   routine, which can't be exercised live here — see spec Assumptions on
   Apps Script's equivalent untestable-here gap), demonstrate the
   resumable-upload recipe against a file at least 536,576 bytes and
   confirm round-trip integrity (download what was uploaded, compare
   bytes). Also exercises the open verification note from approach.md §6:
   whether a folder explicitly shared with the service account (not
   created by it) is listable via `drive.file` scope. Depends on Task 6
   (needs the credential provisioned). Satisfies AC8.
