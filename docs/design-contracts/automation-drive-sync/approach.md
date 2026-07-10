# automation-drive-sync — Design

## Approach

### 1. `import-jsonl`: line-by-line, one bad line doesn't stop the batch

**Decision.** `automation/cli.py`, new `_cmd_import_jsonl`: read the file
line by line (not `json.load` on the whole file — a single malformed line
must not prevent parsing the rest, which a whole-file JSON parse would
make impossible). For each line: `json.loads`, validate the required keys
are present (`message_id`, `thread_id`, `source`, `subject`, `received_at`,
`snippet`), skip with a counted warning on `JSONDecodeError` or a missing
key, otherwise build a `Candidate` (stamping `ingested_at` with the current
UTC time at import) and call `store.add()`. Track three counters (`added`,
`already_present`, `skipped`) and print a one-line summary at the end.

No new store method needed — this is purely a CLI-layer loop over the
existing `add()`, which already carries the injection-guard screen (AC1's
"inherited, not reimplemented" is true by construction, not by extra
code).

### 2. Well-known Drive filenames, fixed and documented

**Decision.** Two fixed names, used verbatim by both the routine doc and
the Apps Script:

- `agentalloy-automation-candidates.db` — the routine's persistent store.
- `agentalloy-automation-newsletter-export.jsonl` — the Apps Script's
  output, one JSON object per line, appended to over time.

Fixed names (not a config file) because the routine and the Apps Script are
two independently-deployed systems with no shared config mechanism between
them — a literal, hardcoded convention in both is simpler and more
reliable than trying to keep a shared config file in sync across two
unrelated deployment surfaces.

### 3. Drive-sync routine: download, import, evaluate, upload — in that order

**Decision.** `automation/routines/scheduled-drive-sync.md` specifies,
literally:

1. Search Drive for `agentalloy-automation-candidates.db`; download it to
   `.automation/candidates.db` if found, otherwise proceed with no local
   file (the store's own `CREATE TABLE IF NOT EXISTS` handles first-run
   creation — no special-casing needed here, another place idempotent
   design absorbs a coordination problem for free).
2. Search Drive for `agentalloy-automation-newsletter-export.jsonl`;
   download it. If absent, there's nothing to import — skip to step 5
   (upload whatever local state exists, which may be nothing on a genuine
   first run).
3. Run `uv run python -m automation.cli ingest import-jsonl <path>`.
4. Follow the existing, unchanged `evaluate-candidate.md` routine against
   `ingest list --status new` (this step is a reference to the existing
   routine, not new instructions — the spec's Out of Scope is explicit that
   evaluation logic itself doesn't change).
5. Upload `.automation/candidates.db` back to Drive, overwriting the
   well-known file.

### 4. Apps Script: label-based dedup, append-only export

**Decision.** `automation/appsscript/newsletter-export.gs`: build a Gmail
query from a hardcoded allowlist (mirrors `sources.yaml`'s sender list,
maintained separately — Apps Script has no access to the repo's local
config file), excluding a dedup label:
`{from:sender-one from:sender-two ...} -label:agentalloy-automation-exported`.
For each match: build one JSON object matching `import-jsonl`'s expected
fields exactly (`message_id` from `GmailMessage.getId()`, `thread_id` from
`getThread().getId()`, `source` from `getFrom()`, `subject` from
`getSubject()`, `received_at` from `getDate().toISOString()`, `snippet`
from a truncated `getPlainBody()`), append one line to the Drive export
file (create it if absent), then apply the
`agentalloy-automation-exported` label to the message so it's excluded
from future runs. Companion setup doc walks through: creating the script
project at script.google.com, pasting the code, authorizing Gmail +
Drive scopes (Jay's own consent), and setting a time-based trigger.

This mirrors `sources.yaml`'s allowlist-driven, deterministic query
approach — the same "explicit config, not classification" philosophy —
just re-expressed in Apps Script's own syntax since it can't read the
Python repo's config file.

### 5. No `--dry-run` flag

**Decision.** Not required by any AC; `ingest list` after a real
`import-jsonl` run already shows exactly what landed, at effectively zero
cost since `add()` is fully idempotent (a real run and a hypothetical "dry"
one would produce the identical end state either way — there's nothing a
dry-run would reveal that a real run doesn't already show safely).

## Non-goals carried from spec

No `store.py` schema/logic changes. No reconciliation between a human's
local db and the routine's Drive-hosted one. No export-file cleanup. No
Discord wiring. No change to how `evaluate-candidate.md` itself works.
