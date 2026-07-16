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

**Reopened, 2026-07-14: a third gap, in the upload mechanism itself.**
`drive-sync-blockers.md` fixed the routine's missing `allowed_tools` entries
(steps 1/2/6 had no callable Drive tool on any prior run), which was a
precondition for the routine ever reaching step 6 at all. But step 6's
actual mechanism — `mcp__Google-Drive__create_file`, called with the local
db's bytes inline as its `base64Content` argument — was never checked
against a realistic file size. The local `.automation/candidates.db`, after
one real evaluation batch, is 536,576 bytes; base64-encoding that inline
means the tool call's argument payload is itself roughly 715,000 characters.
That's not a Drive API limit (Drive's resumable/multipart upload handles
files far larger) — it's the ceiling on how much can go into a single MCP
tool-call argument, and it will only get worse as the store accumulates
more candidates run over run. This was caught directly in this session by
inspecting the tool call shape before ever reaching the live trigger, not
from an observed production failure — but it would have failed the first
time step 6 actually ran with real data. See Design surface for candidate
fixes.

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
- **The storage engine is not the bottleneck — the transport is.** Swapping
  `sqlite` for a different local engine (DuckDB, or embedded Postgres) would
  produce a file of similar or larger size and hit the exact same MCP
  tool-call payload ceiling on upload; it doesn't touch the actual failure.
  A standing Postgres server would additionally require new, always-on
  infrastructure the routine connects to every run — a materially bigger
  commitment than anything this pipeline has needed so far, for no benefit
  against this specific problem. Any redesign here targets *how the bytes
  get to Drive*, not what they're stored in locally.
- **A direct call to the Drive REST API (bypassing the `create_file` MCP
  tool for the upload step specifically) is the leading candidate** —
  Drive's resumable/multipart upload exists precisely for files too large
  for one request, and calling it from `Bash`/`curl` means the file's bytes
  never have to pass through a tool-call argument at all. This needs its
  own credential (an OAuth token or service-account key scoped to
  `drive.file`, ideally to just this one file) living in the routine's
  environment config — the same "routine-only secret, never typed or
  entered by Claude" pattern already established for `GH_DISPATCH_TOKEN`
  and the Discord webhook URL, and the same scope-minimization question
  `automation-discord-relay.md` worked through for its own credential.

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
back to Drive (overwrite). **The upload leg's exact mechanism is deferred
to design** (see Design surface) — it is no longer assumed to be a plain
call to the `create_file` MCP tool, since that tool's inline-base64
argument doesn't scale to the store's real size.

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
8. **The upload mechanism works at realistic file size.** Whatever design
   is chosen for step 6 must be demonstrated (live, against the real Drive
   connector) uploading a `candidates.db` at least as large as the current
   local one (536,576 bytes as of 2026-07-14) without hitting a payload
   ceiling. A fixture that only tests a near-empty database does not
   satisfy this AC — the whole point is proving the fix holds at the size
   that actually broke the naive approach.
9. **No credential introduced for this fix has broader scope than
   uploading/overwriting one named file in Drive.** Same bar as
   `automation-discord-relay.md`'s AC1 for its own credential — verifiable
   by inspecting whatever token/key the chosen design introduces against
   its documented minimum required scope.

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
- **Changing the local storage engine** (sqlite → DuckDB, embedded or
  standing Postgres, or anything else). Established in Assumptions: this
  would not fix the actual failure and, for a standing Postgres server
  specifically, would introduce new always-on infrastructure with no
  offsetting benefit against this problem.
- **Provisioning any new standing infrastructure** (a relay endpoint, a
  hosted service, etc.) without a separate explicit go-ahead from Jay at
  the time it would actually be created — same bar as
  `automation-discord-relay.md`'s equivalent Out of Scope item.
- **Truncating, compacting, or otherwise reducing the candidate store's
  on-disk size.** Whatever fixes the upload leg needs to work at the
  store's actual and growing size, not shrink the problem instead of
  solving it.

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
- **The step-6 upload mechanism, now that `create_file`'s inline-base64
  argument is known not to scale.** Leading candidate: call the Drive REST
  API's resumable/multipart upload endpoint directly from the routine's
  `Bash` tool (`curl`), authenticated with a credential scoped to
  `drive.file` (ideally further scoped to just this one file, via a
  service account with access granted to only that Drive file rather than
  the whole Drive). Design should confirm exactly which auth flow is
  practical for a `RemoteTrigger` routine's Bash environment — a
  long-lived OAuth refresh token vs. a service-account key are different
  operational commitments, and the choice affects where/how that
  credential is provisioned (same routine-only-config pattern as
  `GH_DISPATCH_TOKEN`).
- **Whether `download_file_content` (step 1) has the same ceiling in
  reverse.** Not yet confirmed either way — downloads return content rather
  than accepting it as an argument, which may not hit the same tool-call
  argument-size wall, but this should be checked rather than assumed safe
  just because step 6 wasn't. If it does, the same REST-direct approach
  likely resolves both legs with one credential.
- **Whether the fix should replace `create_file` entirely or only apply
  above some size threshold.** A hybrid (small files via the existing MCP
  tool, large ones via REST) adds a branch design must justify; a single
  REST-direct path for step 6 regardless of size is simpler and doesn't
  regress silently as the store grows — this is a real design decision,
  not dictated by this spec.
