# Routine: scan-slack-links

Followed by an agent with Slack MCP access (`claude.ai Slack`) — either an
interactive Claude Code session, or a `RemoteTrigger` scheduled routine
whose environment starts from a fresh git clone every run (same model as
`scheduled-drive-sync.md`). Every step below is literal — no judgment calls
beyond reading matched message content to fill in the extracted fields.

## Environment requirements

Like `scheduled-drive-sync.md`, this routine round-trips its candidate store
through Drive so URLs found in one hourly run survive into the next (and
into the daily Drive Sync digest). Requires the same routine-only config,
provisioned by Jay per `automation/docs/drive-sync-credential-setup.md`:

- `DRIVE_SERVICE_ACCOUNT_EMAIL`
- `DRIVE_SERVICE_ACCOUNT_PRIVATE_KEY`
- `DRIVE_FOLDER_ID`

Plus `openssl`, `curl`, and `jq` on the routine's runner. See
`scheduled-drive-sync.md`'s own Environment requirements section for the
exact formatting rules for these values — not repeated here.

## 0. Obtain a Drive access token, then download the candidate store

Same recipe as `scheduled-drive-sync.md`'s "Obtaining a Drive access token"
and step 1, scoped to just the candidates file (this routine has no
newsletter export to fetch):

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

mkdir -p .automation
CANDIDATES_FILE_ID=$(find_file agentalloy-automation-candidates.db)
if [ -n "$CANDIDATES_FILE_ID" ]; then
  download_file "$CANDIDATES_FILE_ID" .automation/candidates.db
fi
```

If `agentalloy-automation-candidates.db` isn't found (the very first run
ever), proceed with no local file — `CandidateStore` creates the schema
itself on first use.

## 1. Get the cursor

```
uv run python -m automation.cli ingest slack-cursor get
```

Prints the last-processed Slack message `ts` (a Slack timestamp string, e.g.
`"1721904000.123456"`), or nothing if this is the first run. Keep this
value; it's the low-water mark for step 3.

## 2. Fetch messages

Get `channel_id` and `author_user_id` first from `automation/config/slack.yaml`
if it exists (local, gitignored — not committed to this repo; present in an
interactive session's checkout). If that file doesn't exist (a scheduled
`RemoteTrigger` run's fresh clone never has it), use the `channel_id` and
`author_user_id` given directly in this routine's own trigger prompt instead
— neither value is a secret (a Slack channel ID and a Slack user ID, not a
credential), so they're provided inline in the scheduled trigger's config
rather than requiring routine-only env vars the way `scheduled-drive-sync.md`
does for its actual credentials.

Call `slack_read_channel` for that `channel_id` with a `limit` of 100 —
enough to cover any reasonable gap between scans. This returns messages
newest-first; each message has `ts`, `user`, and `text` fields (standard
Slack message shape).

## 3. Filter to Jay's messages newer than the cursor

Keep only messages whose `user` equals `author_user_id` (never Claude's own
`slack_send_message` output, never anyone else's messages) whose `ts` is
greater than the cursor from step 1 (or all of Jay's messages, if no cursor
is set yet). Compare `ts` values as floats — Slack timestamps are
`<epoch-seconds>.<microseconds>` strings, not directly string-orderable
across differing lengths.

If no messages remain after filtering, skip to step 6 and report zero
activity — do not advance the cursor (there's nothing new to advance it to).

## 4. Extract links per message

Messages from step 2 are newest-first; process them in ascending `ts` order
(oldest first). For each remaining message:

1. Write the message's `text` to a temp file.
2. Run:
   ```
   uv run python -m automation.cli ingest extract-links --text-file <path> --cap 5
   ```
   (`--text-file`, not `--text`, so arbitrary message content never has to be
   interpolated into a shell command line.)
3. Track a running total of extracted URLs against a per-run cap of 20. Once
   the run cap is reached, stop adding new URLs — keep processing the
   remaining messages only to count/report their skips, don't call `add-url`
   for them.

## 5. Record each extracted URL

For every URL extracted in step 4 (up to the per-run cap), convert the
message's `ts` to ISO 8601:

```
uv run python -c "import datetime, sys; print(datetime.datetime.fromtimestamp(float(sys.argv[1]), tz=datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'))" "<ts>"
```

then run:

```
uv run python -m automation.cli ingest add-url \
  --url "<url>" \
  --subject "<first ~60 chars of the message that contained it>" \
  --received-at "<converted ISO 8601 timestamp>" \
  --source slack
```

## 6. Advance the cursor

Only after every message in this run has been processed without error,
advance the cursor to the newest `ts` seen this run:

```
uv run python -m automation.cli ingest slack-cursor set --message-id "<newest ts>"
```

Advancing only on full success means a mid-run failure (e.g. a store I/O
error) leaves the cursor where it was, so a retry reprocesses from the same
point rather than silently skipping a message — `add-url`'s dedup makes that
retry safe (already-added URLs no-op rather than duplicate).

## 7. Report

Report: candidates added, already-present skips, per-message cap skips
(URLs beyond the 5-per-message cap), and per-run cap skips (URLs beyond the
20-per-run cap after it was reached).

## 8. Upload the candidate store back to Drive

Same resumable-upload recipe as `scheduled-drive-sync.md`'s step 5, scoped
to just the candidates file. Run this even if step 3 short-circuited to a
zero-activity report — the upload is then a safe no-op / overwrite with
identical content:

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

## Notes

- This routine and `scheduled-drive-sync.md` both read-modify-write the
  same Drive-hosted `candidates.db`, and land only ~11 minutes apart on the
  day Drive Sync runs (`23 * * * *` vs `12 11 * * *`). An overlapping write
  could clobber the other's changes if either run ever took longer than
  that gap. Accepted as a low-probability risk rather than adding
  locking/retry logic — consistent with this codebase's pattern of fixing
  real incidents as they occur (see `scheduled-drive-sync.md`'s own Notes)
  rather than pre-engineering for a narrow, unconfirmed race.
