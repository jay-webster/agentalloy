# Routine: scheduled-drive-sync

Followed by a `RemoteTrigger` cloud routine, whose environment starts from
a fresh git clone every run and has no memory of prior runs beyond what it
explicitly fetches. Drive access is REST-direct via a service-account
credential (see Environment requirements) — this routine does **not** use
a Google Drive MCP connector or any `mcp__Google-Drive__*` tool (Gmail is
not available to routines either — see the drive-sync spec for why this
routine exists at all).

## Environment requirements

Requires three pieces of routine-only config, provisioned by Jay per
`automation/docs/drive-sync-credential-setup.md` — never committed to this
repo and never typed or entered by an interactive Claude session:

- `DRIVE_SERVICE_ACCOUNT_EMAIL` — the service account's `client_email`.
- `DRIVE_SERVICE_ACCOUNT_PRIVATE_KEY` — the service account's `private_key`
  field, copied verbatim as the single-line, `\n`-escaped string it already
  is inside the downloaded JSON key (not reformatted into real line breaks —
  the JWT step below expands the escapes with `printf '%b'` at sign time).
- `DRIVE_FOLDER_ID` — the ID of the `agentalloy-automation` Shared Drive
  (or a folder inside it), which must already be shared with the service
  account's email, role Content Manager. Must be a Shared Drive, not a
  folder in a personal My Drive — see Notes, "Storage quota, discovered
  2026-07-15".

Also requires `openssl`, `curl`, and `jq` on the routine's runner (all
standard on `ubuntu-latest`-class environments; no new dependency beyond
what `discord-digest-relay.yml` already assumes for step 5).

## Obtaining a Drive access token

Done once, at the top of every run, before steps 1 and 5:

```
NOW=$(date +%s)
EXP=$((NOW + 3600))

b64url() { openssl base64 -e -A | tr '+/' '-_' | tr -d '='; }

JWT_HEADER=$(printf '{"alg":"RS256","typ":"JWT"}' | b64url)
JWT_CLAIMS=$(jq -nc \
  --arg iss "$DRIVE_SERVICE_ACCOUNT_EMAIL" \
  --arg scope "https://www.googleapis.com/auth/drive.file" \
  --arg aud "https://oauth2.googleapis.com/token" \
  --argjson iat "$NOW" --argjson exp "$EXP" \
  '{iss: $iss, scope: $scope, aud: $aud, iat: $iat, exp: $exp}' | b64url)

JWT_UNSIGNED="${JWT_HEADER}.${JWT_CLAIMS}"
JWT_SIGNATURE=$(printf '%s' "$JWT_UNSIGNED" \
  | openssl dgst -sha256 -sign <(printf '%b' "$DRIVE_SERVICE_ACCOUNT_PRIVATE_KEY") \
  | b64url)
JWT="${JWT_UNSIGNED}.${JWT_SIGNATURE}"

ACCESS_TOKEN=$(curl -sS -X POST https://oauth2.googleapis.com/token \
  -d grant_type=urn:ietf:params:oauth:grant-type:jwt-bearer \
  -d assertion="$JWT" | jq -r '.access_token')
```

`drive.file` is the narrowest available Drive OAuth scope; the Shared
Drive membership (not the scope name) is what makes this credential's
access boundary a Drive-ACL fact instead of a code-behavior claim — see
AC9.

## 1. Download the candidate store and the newsletter export

Both files are found and fetched the same way — one list call, one
conditional download, against `agentalloy-automation-candidates.db` and
`agentalloy-automation-newsletter-export.jsonl` in turn:

```
find_file() {  # $1 = well-known name
  curl -sS -G https://www.googleapis.com/drive/v3/files \
    -H "Authorization: Bearer $ACCESS_TOKEN" \
    --data-urlencode "q=\"$DRIVE_FOLDER_ID\" in parents and name = '$1' and trashed = false" \
    --data-urlencode "fields=files(id)" \
    --data-urlencode "supportsAllDrives=true" \
    --data-urlencode "includeItemsFromAllDrives=true" \
    | jq -r '.files[0].id // empty'
}

download_file() {  # $1 = file id, $2 = local path
  curl -sS -o "$2" -H "Authorization: Bearer $ACCESS_TOKEN" \
    "https://www.googleapis.com/drive/v3/files/$1?alt=media&supportsAllDrives=true"
}

CANDIDATES_FILE_ID=$(find_file agentalloy-automation-candidates.db)
if [ -n "$CANDIDATES_FILE_ID" ]; then
  download_file "$CANDIDATES_FILE_ID" .automation/candidates.db
fi
```

If `agentalloy-automation-candidates.db` isn't found (the very first run
ever), proceed with no local file — `CandidateStore` creates the schema
itself on first use, so there's nothing special to do here.

```
EXPORT_FILE_ID=$(find_file agentalloy-automation-newsletter-export.jsonl)
if [ -n "$EXPORT_FILE_ID" ]; then
  download_file "$EXPORT_FILE_ID" .automation/newsletter-export.jsonl
fi
```

If the newsletter export isn't found, there is nothing new to import —
skip step 2 and continue to step 3 anyway (it will simply find no
`status=new` candidates, and step 4's report will correctly say so — this
still confirms to Jay that the routine ran).

## 2. Import

```
uv run python -m automation.cli ingest import-jsonl "<downloaded export path>"
```

This is safe to run even if some or all entries were already imported on a
prior run — `add()` is idempotent by `message_id`.

## 3. Evaluate

Before running any evaluation, capture the current time:

```
SINCE=$(date -u +%Y-%m-%dT%H:%M:%SZ)
```

Then follow `automation/routines/evaluate-candidate.md` (unchanged,
referenced here rather than duplicated) against `uv run python -m
automation.cli ingest list --status new`.

## 4. Relay the report to Discord via GitHub (best-effort — never blocks step 5)

Run:

```
uv run python -m automation.cli ingest report --since "$SINCE"
```

This environment's network egress policy blocks `discord.com` directly
(confirmed `403`, see Notes), so the report is relayed through a GitHub
Actions workflow (`discord-digest-relay.yml`, running on `ubuntu-latest`,
which has unrestricted egress) instead of posted to Discord directly.
Dispatch it with a `repository_dispatch` event, authenticated with
`GH_DISPATCH_TOKEN` (routine-only config, provisioned by Jay — never
committed to this repo and never typed or entered by Claude):

```
jq -n --arg report "$(uv run python -m automation.cli ingest report --since "$SINCE")" '{event_type: "discord-digest", client_payload: {report: $report}}' \
  | curl -sS -X POST \
      -H "Authorization: Bearer $GH_DISPATCH_TOKEN" \
      -H "Accept: application/vnd.github+json" \
      -d @- "https://api.github.com/repos/jay-webster/agentalloy/dispatches"
```

The `jq -n --arg` step correctly JSON-escapes the digest text (newlines,
quotes) — don't hand-build the JSON payload string directly.

**If this `curl` fails for any reason (including an auth or network
failure — the same class of real, confirmed failure mode that used to
hit `discord.com` directly, not hypothetical), do not stop the routine
and do not skip step 5.** Note the failure in the final report and
continue. A notification delivery failure says nothing about whether the
evaluation data itself is valid — gating persistence on it was a real bug
(see Notes) that lost a full run's evaluations (486 candidates) the first
time this environment's egress policy actually blocked the request.

## 5. Upload the candidate store back to Drive

Upload `.automation/candidates.db`, overwriting
`agentalloy-automation-candidates.db` in Drive, **as long as steps 1-3
completed without error — independent of whether step 4 (Discord)
succeeded.** This is the only step that matters for the *database* state
to persist into the next scheduled run; a real evaluation batch (486/486
processed, 0 errors) is valid, persistable data regardless of whether the
notification about it happened to get delivered. If steps 1-3 genuinely
failed (corrupt import, a crash mid-evaluation), do NOT upload — stop and
report the error instead, so a partial or corrupt *data* state is never
persisted. A failed Discord POST is not that — see step 4.

Resumable upload, streamed from disk — never buffered as base64 in any
argument, which is what removes the payload-size ceiling that broke the
old `create_file`-based transport (see Notes):

```
if [ -n "$CANDIDATES_FILE_ID" ]; then
  LOCATION=$(curl -sS -X PATCH \
    -H "Authorization: Bearer $ACCESS_TOKEN" \
    "https://www.googleapis.com/upload/drive/v3/files/$CANDIDATES_FILE_ID?uploadType=resumable&supportsAllDrives=true" \
    -D - -o /dev/null | grep -i '^location:' | tr -d '\r' | cut -d' ' -f2-)
else
  LOCATION=$(curl -sS -X POST \
    -H "Authorization: Bearer $ACCESS_TOKEN" \
    -H "Content-Type: application/json; charset=UTF-8" \
    "https://www.googleapis.com/upload/drive/v3/files?uploadType=resumable&supportsAllDrives=true" \
    -d "{\"name\": \"agentalloy-automation-candidates.db\", \"parents\": [\"$DRIVE_FOLDER_ID\"]}" \
    -D - -o /dev/null | grep -i '^location:' | tr -d '\r' | cut -d' ' -f2-)
fi

curl -sS -T .automation/candidates.db "$LOCATION"
```

On first run (`CANDIDATES_FILE_ID` empty), the `POST` branch creates the
file inside the Shared Drive; the file's storage counts against the
Shared Drive's own quota (not the service account's, which is zero — see
Notes) and no separate manual share is needed for this specific file
beyond the one-time Shared Drive membership already covering it (see
Environment requirements).

## Notes

- The newsletter export file is not cleared or truncated by this routine —
  it grows over time on the Apps Script side (see
  `automation/appsscript/`). Re-importing old entries is harmless (step 2's
  idempotency) but not free; this is an accepted, low-urgency limitation
  given expected volume.
- This routine's Drive-hosted `candidates.db` is a separate, canonical copy
  for the routine's own use — it is not synced with any human's local
  `.automation/candidates.db` from an interactive session.
- **Real incident, 2026-07-12**: `discord.com` returned a `403` from this
  environment's network egress policy on the routine's very first
  Discord-enabled run, and the upload step was (at the time) gated on the
  Discord step succeeding — so a full, clean evaluation batch (486
  candidates: 11 accept, 32 needs_review, 443 reject, 0 errors) was never
  uploaded to Drive and was lost when the session ended. Fixed by
  decoupling the upload step from the Discord step's outcome (see step 5
  above). The underlying `discord.com` egress block is still unresolved —
  either the environment's egress policy needs `discord.com` allowed, or
  Discord delivery for this routine needs a different path entirely (e.g.
  bridging through the already-working GitHub Actions webhook delivery
  used by `pr-digest.yml`, which runs in a different, unrestricted network
  environment). Not yet decided.
- **Separate real incident, discovered 2026-07-14, fixed same day**: with
  the (now-replaced) MCP-connector transport, the live trigger's
  `mcp_connections` had a `Google-Drive` connector attached, but
  `session_context.allowed_tools` never actually listed any Drive MCP tool
  name — so steps 1/2/6 (as numbered at the time) had no callable tool on
  *every* run to date, and `agentalloy-automation-candidates.db` had never
  once been created in Drive. Every run was silently re-importing and
  re-evaluating from an empty local store. **Superseded, 2026-07-14, by
  the REST-direct transport above**: this routine no longer attaches a
  Drive MCP connector or depends on `allowed_tools`/`permitted_tools`
  configuration at all, so this entire failure mode no longer applies —
  recorded here only as history, not as a live risk.
- **Transport fix, 2026-07-14**: replaced the MCP-tool-based Drive access
  (steps 1, 2, and the upload step, all `mcp__Google-Drive__*` calls) with
  the REST-direct, service-account-authenticated recipe above, because the
  original `create_file` MCP tool's inline-base64 argument had a payload
  ceiling that broke on a realistic-size `candidates.db`. See
  `docs/design/automation-drive-sync/approach.md` §6 for the full
  rationale and the OAuth-vs-service-account tradeoff.
- **Storage quota, discovered 2026-07-15**: the live proof (task 7) first
  ran against a folder in a personal My Drive account and failed the
  resumable upload with `403 storageQuotaExceeded` — "Service Accounts do
  not have storage quota." A service account has zero storage quota of
  its own in My Drive; being an Editor on someone else's folder doesn't
  change that, since a newly-created file's storage attaches to its
  creator, not the folder owner. Fixed by moving `agentalloy-automation`
  to a Shared Drive (Workspace-only — not available on personal Gmail
  accounts) whose storage is pooled at the drive level, and adding
  `supportsAllDrives=true`/`includeItemsFromAllDrives=true` to every
  list/download/upload call above (required for the API to see Shared
  Drive content at all; omitting them makes the Shared Drive invisible to
  these calls rather than erroring). The access-boundary intent from §6 —
  narrow `drive.file` scope, one inspectable share, nothing else reachable
  — is unchanged; only the sharing mechanism (Shared Drive membership,
  role Content Manager, instead of a My Drive folder share, role Editor)
  and these query params changed.
