# Automation Drive Sync — Spec

> **Scope in a sentence.** Give a scheduled cloud routine a way to persist
> the candidate store across runs (via a Drive-hosted copy of the same
> sqlite file) and a deterministic way to import newsletter matches a
> Google Apps Script exports from Gmail — closing the gap between "the
> pipeline works when a human runs it" and "the pipeline runs unattended."

> **Location note.** At runtime the SDD spec phase writes the spec to
> `docs/spec/automation-drive-sync.md`, git-ignored. This file is the
> committed, reviewable copy.

## Context

Checking whether the pipeline could run on a schedule (via `RemoteTrigger`
cloud routines) surfaced two real gaps, in order:

1. **Gmail isn't an available connector for routines** — confirmed via the
   `/schedule` skill's own connector list (Drive, Calendar, Gamma,
   SlidesGPT are available; Gmail, though connected and working in
   interactive sessions, is not). Chosen resolution (Jay's explicit
   direction): bridge via Google Drive — a Google Apps Script running
   under Jay's own account (native Gmail access, its own triggers,
   entirely outside Claude) exports matching newsletter content into a
   Drive file; the Claude routine reads Drive instead of Gmail directly.
2. **A routine's cloud environment starts from a fresh git clone every
   run** — `.automation/candidates.db` is local and git-ignored by design
   (slice 1), so a routine never sees prior state. Without a persistence
   mechanism, every scheduled run would start blind, unable to tell "new"
   from "already processed."

This spec addresses both, using the same "deterministic component + a
routine any capable agent can execute" split every prior slice has used —
except this time the "agent with the needed access" is a scheduled cloud
routine, not this interactive session.

## Assumptions (correct these before design)

- **No changes to `automation/store.py`'s schema or core logic.** Every
  candidate — however it reaches the store — already goes through
  `add()`, which already runs the injection-guard screen (slice 3). A new
  ingestion path does not need to reimplement that; it inherits it for
  free by calling the same method.
- **The routine's Drive-hosted `candidates.db` is a separate, canonical
  copy for the routine's own use** — not synced back to any human's local
  `.automation/candidates.db`. Reconciling routine state with local
  human-session state is explicitly deferred (see Out of Scope); this slice
  only needs the routine to have *a* persistent, working copy across its
  own runs.
- **Apps Script code is real but untestable by this session.** It runs
  under Jay's own Google account, requires his own OAuth consent to deploy,
  and there is no tool here that can execute or verify Apps Script code
  live. This slice's QA for that half will be "verified by code review, not
  a live run" — an honest, unavoidable gap (unlike the earlier-tonight
  precedent where installing a missing local dependency turned an
  avoidable inspection-only gap into a real one; there is no equivalent
  fix available here).
- **The export format is the seam between the two untestable and testable
  halves** — get this precise so the Apps Script (untestable here) and the
  import command (fully testable here) agree without needing to test them
  together.
- **Idempotency absorbs the sync problem**, the same way it already did for
  slice 1's dedup-by-message_id: the Apps Script can safely re-export
  candidates the import side has already seen (or the import side can
  safely re-process a file it's seen before) without needing coordinated
  "mark as consumed" state between two independently-scheduled systems.

## What

**Import command.** `automation/cli.py`: `ingest import-jsonl <path>` —
reads a file where each line is a JSON object with fields `message_id`,
`thread_id`, `source`, `subject`, `received_at`, `snippet` (the same fields
`ingest add` already takes, minus `ingested_at`, which the importer stamps
itself at import time — the exporter doesn't need to know about that
field's semantics). Calls `store.add()` for each line. A malformed line is
skipped with a warning, not a batch-aborting exception — one bad row
doesn't block the rest, matching the standing "one bad input doesn't block
the batch" convention. Prints a summary: counts added / already-present /
skipped.

**Drive-sync routine.** `automation/routines/scheduled-drive-sync.md` — the
literal instructions a `RemoteTrigger` cloud routine follows each
scheduled run: download `candidates.db` from a well-known Drive filename
(create fresh if this is the first run ever), download the newsletter
export file from a second well-known Drive filename, run `ingest
import-jsonl` against it, run the existing `evaluate-candidate.md` routine
over newly-imported candidates, then upload the modified `candidates.db`
back to Drive (overwrite).

**Apps Script.** `automation/appsscript/newsletter-export.gs` (plus a
setup doc) — JavaScript Jay deploys himself via script.google.com. Searches
Gmail against an allowlist (mirrors `sources.yaml`'s shape, maintained
separately since Apps Script can't read the local repo), excludes
already-exported messages via a Gmail label, appends matches to the
well-known Drive export file in the JSONL format the import command
expects, then applies the label so the same message isn't re-exported.

## Acceptance Criteria

1. **`import-jsonl` adds every well-formed line**, each going through the
   existing `add()` path (idempotent, injection-screened — inherited, not
   reimplemented). Verifiable by a unit test with a multi-line JSONL
   fixture, asserting all rows land in the store correctly, including one
   that would trip the injection guard, asserting it's flagged exactly like
   a directly-added candidate would be.
2. **A malformed line is skipped, not fatal.** A JSONL file with one
   invalid line (bad JSON, or missing a required field) among otherwise
   valid ones: the valid lines are still imported, the bad line is reported
   in the summary, the command doesn't crash. Verifiable by a unit test.
3. **Re-importing the same file is safe.** Running `import-jsonl` twice on
   an unchanged file results in the same store state as running it once
   (relies on `add()`'s existing idempotency — this AC exists to prove the
   import command doesn't add its own accidental duplication path, e.g. by
   generating a new synthetic id per import rather than reusing the JSONL's
   own `message_id`). Verifiable by a unit test.
4. **Summary output is accurate.** Counts of added / already-present /
   skipped match the actual outcome for a fixture with all three cases
   present. Verifiable by a unit test.
5. **No product code touched, no new dependency, no LLM call in the import
   command.** Same bar as every prior slice — zero diff under
   `src/agentalloy/`; `import-jsonl` uses only stdlib `json`.
6. **Export format is fully specified and consistent** between the Apps
   Script (`newsletter-export.gs`) and what `import-jsonl` expects — same
   field names, same types, verifiable by inspecting both files' field
   lists side by side (this is the seam an automated test can't cross, so
   it's a documentation/inspection AC, not a runtime one).
7. **Live proof (of the testable half).** A JSONL fixture shaped exactly
   like what the Apps Script would produce (constructed by hand, not by
   running the Apps Script) is imported via the real CLI against a fresh
   store in this session, and the resulting candidates are shown via
   `ingest list` — proving the import half works against realistic data,
   even though the export half can't be live-proven here.

## Out of Scope

- **Actually creating/enabling the `RemoteTrigger` routine.** A real,
  standing-configuration action taken after this slice ships, with
  explicit go-ahead at the time — not part of this build.
- **Actually deploying the Apps Script** into Jay's Google account. Jay
  does this himself, following the setup doc; not something this session
  can do on his behalf (his own OAuth consent, his own account).
- **Reconciling a human's local `.automation/candidates.db` with the
  routine's Drive-hosted copy.** They remain separate, disconnected copies
  for now — a real question, deliberately deferred (see Assumptions).
- **Export file cleanup or truncation** on the Drive side. The file grows
  over time; accepted as a low-urgency limitation given expected volume
  (a handful of newsletters/day), not solved by this slice.
- **Discord/notification wiring** for results of an unattended run — still
  unresolved from earlier slices, not newly in scope here.
- **Running the evaluator's actual judgment autonomously as part of the
  routine without any further design.** The drive-sync routine *invokes*
  the existing `evaluate-candidate.md` routine (unchanged) — this slice
  does not change how evaluation itself works, only how a cloud routine
  gets state in and out.

## Design surface (hand-off to the design phase)

- **Well-known Drive filenames** — fixed, documented names for the two
  Drive files (candidates db, newsletter export), created on first use if
  absent.
- **Apps Script's own dedup mechanism** — a Gmail label applied after
  export, matching the shape of `sources.yaml`'s allowlist-driven query
  but run under Jay's own Google account/triggers, not Claude.
- **Whether `import-jsonl` needs a `--dry-run` or similar inspection mode**
  — not required by any AC, but worth a design-phase judgment call on
  whether it's cheap enough to add now vs. genuinely unnecessary scope.
