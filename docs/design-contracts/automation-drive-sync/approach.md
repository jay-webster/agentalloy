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

**Decision.** Two fixed names, both living inside one fixed folder, used
verbatim by both the routine doc and the Apps Script:

- `agentalloy-automation/` — the shared folder (see §6 for why a folder,
  not two loose files at Drive's root).
- `agentalloy-automation/agentalloy-automation-candidates.db` — the
  routine's persistent store.
- `agentalloy-automation/agentalloy-automation-newsletter-export.jsonl` —
  the Apps Script's output, one JSON object per line, appended to over
  time.

Fixed names (not a config file) because the routine and the Apps Script are
two independently-deployed systems with no shared config mechanism between
them — a literal, hardcoded convention in both is simpler and more
reliable than trying to keep a shared config file in sync across two
unrelated deployment surfaces.

**Update, 2026-07-14 (reopened spec, third gap).** The single-folder
addition above post-dates the transport fix in §6. §6 introduces a
service-account credential that needs read/write access to *both*
well-known files — including the newsletter export, which lives in Jay's
own Drive because the Apps Script runs under his account, not the service
account's. A shared folder is the natural unit to grant that access to
once, rather than sharing two loose files individually or granting the
service account broader Drive-wide access. This changes where the files
live but not their names or format.

### 3. Drive-sync routine: download, import, evaluate, upload — in that order

**Decision.** `automation/routines/scheduled-drive-sync.md` specifies,
literally:

1. **(Updated, see §6 — no longer an MCP tool call.)** REST-list the
   `agentalloy-automation/` folder, REST-download
   `agentalloy-automation-candidates.db` to `.automation/candidates.db` if
   found, otherwise proceed with no local file (the store's own `CREATE
   TABLE IF NOT EXISTS` handles first-run creation — no special-casing
   needed here, another place idempotent design absorbs a coordination
   problem for free).
2. **(Updated, see §6.)** REST-download
   `agentalloy-automation-newsletter-export.jsonl` from the same folder. If
   absent, there's nothing to import — skip to step 5 (upload whatever
   local state exists, which may be nothing on a genuine first run).
3. Run `uv run python -m automation.cli ingest import-jsonl <path>`.
4. Follow the existing, unchanged `evaluate-candidate.md` routine against
   `ingest list --status new` (this step is a reference to the existing
   routine, not new instructions — the spec's Out of Scope is explicit that
   evaluation logic itself doesn't change).
5. **(Updated, see §6.)** REST-upload `.automation/candidates.db` back to
   the well-known Drive file via resumable upload, overwriting it in
   place.

Steps 1, 2, and 5 (renumbered from the original doc's step 6 — see §6)
no longer call `mcp__Google-Drive__download_file_content` or
`mcp__Google-Drive__create_file` at all; all three now go through the
same REST-direct mechanism and the same credential.

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

### 6. Transport fix: REST-direct via a per-folder-scoped service account, full replacement not a hybrid

**Added, 2026-07-14, resolving the spec's reopened third gap.**

**Decision: service-account credential, scoped by sharing one Drive
folder, not `drive.file`-scoped OAuth.** Two candidates were weighed
(spec's Assumptions named both an OAuth refresh token and a
service-account key as live options):

- **OAuth refresh token, `drive.file` scope.** Simpler token refresh (one
  `curl` to `oauth2.googleapis.com/token` with `grant_type=refresh_token` —
  no request signing), but `drive.file`'s access boundary is *behavioral*
  (whatever files the app happens to create or is handed via Picker), not
  something Drive's own sharing UI can show as an explicit grant list. AC9
  requires the credential's scope to be verifiable by inspection against a
  documented minimum — `drive.file` satisfies this only by trusting the
  code never touches anything else, not by an inspectable ACL.
- **Service account, folder shared with it.** Requires a JWT-bearer token
  exchange (RS256-signing a claims set with the service account's private
  key via `openssl`, then a `curl` to the token endpoint) — more steps than
  a refresh-token POST, but a standard, well-documented Google recipe, not
  bespoke crypto. In exchange, Drive's own sharing dialog on the
  `agentalloy-automation/` folder directly shows the one principal
  (`<service-account>@<project>.iam.gserviceaccount.com`) with access and
  the one resource it's shared to — an AC9 story verifiable by looking at
  the folder's sharing settings, not by trusting application code.

**Chosen: the service account**, because AC9 is a named acceptance
criterion, not a nice-to-have, and "verifiable by inspecting... against
its documented minimum" reads as wanting an ACL-level answer, not a
code-behavior-level one. The extra JWT-signing steps are one-time
tooling, not ongoing operational cost.

**Provisioning (Jay, one-time, mirrors the Apps Script's own
one-time-consent framing elsewhere in this spec):**

1. Create a Google Cloud project (or reuse one), enable the Drive API,
   create a service account, generate a JSON key.
2. Create the `agentalloy-automation/` folder in Jay's own Drive, share it
   with the service account's email, role Editor.
3. Store the service-account JSON key's `client_email` and `private_key`
   fields as routine-only env config — same "never committed, never typed
   or entered by an interactive Claude session" bar as `GH_DISPATCH_TOKEN`
   and the Discord webhook URL (see `automation-discord-relay.md`'s
   equivalent framing for its own credential).

**Runtime token exchange (every routine run, literal steps in the routine
doc):**

1. Build a JWT claims set: `iss` = service account's `client_email`,
   `scope` = `https://www.googleapis.com/auth/drive.file`, `aud` =
   `https://oauth2.googleapis.com/token`, `iat`/`exp` (1-hour window).
2. Base64url-encode header + claims, sign with `openssl dgst -sha256
   -sign` against the private key, base64url-encode the signature —
   standard RS256 JWT-bearer assertion.
3. `curl -X POST https://oauth2.googleapis.com/token -d
   grant_type=urn:ietf:params:oauth:grant-type:jwt-bearer -d
   assertion=$JWT` → short-lived `access_token`.

`drive.file` is still the scope on the token itself (narrowest available
Drive scope); the folder-share is what makes that scope's boundary
concrete and auditable rather than merely trusted.

**Runtime Drive calls (replacing all three MCP-tool call sites named in
§3):**

- **List/find** (steps 1 and 2): `GET
  https://www.googleapis.com/drive/v3/files?q='<folderId>' in parents and
  name = '<well-known-name>'`, `Authorization: Bearer $ACCESS_TOKEN`.
- **Download** (steps 1 and 2): `GET
  https://www.googleapis.com/drive/v3/files/<fileId>?alt=media`, streamed
  straight to a local path via `curl -o` — never held as a tool-call
  argument or a tool-result payload, just bytes on disk.
- **Upload/overwrite** (step 5, was step 6): `PATCH
  https://www.googleapis.com/upload/drive/v3/files/<fileId>?uploadType=resumable`
  with an empty body to open a resumable session (`Location` response
  header), then `PUT` the file's bytes to that `Location` via `curl -T
  .automation/candidates.db` — streamed directly from disk, never
  buffered as base64 in any argument. This is what satisfies AC8: the
  ceiling that broke `create_file` was specifically the inline-base64
  tool-call argument, and streaming bytes via `curl -T`/`--data-binary`
  has no equivalent argument-size step at all.
- **First run** (candidates.db doesn't exist yet): `POST
  https://www.googleapis.com/upload/drive/v3/files?uploadType=resumable`
  with `parents: [<folderId>]` and the well-known name in the metadata
  body, then the same resumable `PUT`. The service account becomes the
  file's creator/owner on first run — no separate manual share needed for
  this specific file beyond the one-time folder share already covering it.

**Resolving the spec's "does `download_file_content` have the same
ceiling in reverse" question: moot by construction, not answered in the
abstract.** The original concern was specific to `create_file`'s
argument-side ceiling; a tool *result* (what `download_file_content`
returns) isn't subject to the same single-argument JSON-payload
constraint, so it likely would have been fine at current file sizes. But
rather than leave that as a "probably fine, unconfirmed" residual risk
that could resurface as the store grows, replacing both directions with
the same REST-direct mechanism removes the question entirely — one
transport, one credential, no asymmetry to keep re-checking as the file
size grows. This directly matches the spec's own Design-surface framing:
"the same REST-direct approach likely resolves both legs with one
credential."

**Full replacement, not a size-threshold hybrid.** A hybrid (small files
via the existing MCP tools, large ones via REST) would still require
provisioning and maintaining the exact same service-account credential —
it doesn't remove any of the setup cost above — while adding a branch that
must be tested on both sides and that silently flips behavior once the
store crosses whatever threshold is chosen. A single REST-direct path,
used unconditionally regardless of current file size, is simpler and
doesn't have a latent failure mode that reappears later as the store
grows. Chosen per the spec's own framing of this exact tradeoff.

**Verification note for QA/build, not resolved here.** Whether a
`drive.file`-scoped service-account token can successfully `files.list`
by `parents` within a folder explicitly shared with it (rather than a
folder the service account created itself) is a reasonable expectation
under Google's documented per-resource access model, but hasn't been
exercised live from this design pass — flagged as something the live
proof in AC8's testing must actually confirm, not assumed safe by
reasoning alone.

## Non-goals carried from spec

No `store.py` schema/logic changes. No reconciliation between a human's
local db and the routine's Drive-hosted one. No export-file cleanup. No
Discord wiring. No change to how `evaluate-candidate.md` itself works.
