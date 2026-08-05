# Routine: apply-review-queue

Followed by a `RemoteTrigger` routine whose environment starts from a fresh
git clone every run (same model as `scheduled-drive-sync.md` and
`scan-slack-links.md`), fired manually by an interactive Claude Code session
once Jay has confirmed a batch of queued verdicts (see
`automation/review_queue.py`) is ready to apply. This routine never reads
`.automation/review-queue.jsonl` off Jay's machine — it cannot, since it
runs in its own fresh clone. The verdict rows it applies arrive as literal
JSONL content embedded directly in this run's own trigger prompt (see step
2). Every step below is literal — no judgment calls; the verdicts have
already been decided by the interactive session that queued them.

## Environment requirements

Like `scheduled-drive-sync.md` and `scan-slack-links.md`, this routine
round-trips the candidate store through Drive. Requires the same
routine-only config, provisioned by Jay per
`automation/docs/drive-sync-credential-setup.md`:

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

If `agentalloy-automation-candidates.db` isn't found, proceed with no local
file — `CandidateStore` creates the schema itself on first use. In practice
this should never happen for this routine (a queue only exists to apply
verdicts against candidates that already exist), but the fallback is kept
identical to the other two routines for consistency.

## 1. Write the queued verdict rows to a temp JSONL

The verdict rows to apply arrive as literal JSONL content in this run's own
trigger prompt (one `{"message_id", "verdict", "rationale"}` object per
line — the exact shape `review_queue.list_pending()` returns and
`evaluate-batch` already accepts). Write that content, unmodified, to a temp
file:

```
QUEUE_TMP=$(mktemp)
cat > "$QUEUE_TMP" <<'EOF'
<the run's inline JSONL content, verbatim>
EOF
```

Nothing in this step reads from or writes to any file this routine looked
up itself — the rows come only from the prompt content of this specific,
explicitly-fired run.

## 2. Apply the verdicts

Run the existing, unmodified `evaluate-batch` command, pointed at the temp
file from step 1:

```
uv run python -m automation.cli ingest evaluate-batch "$QUEUE_TMP"
```

No new store or CLI logic — this is the same command
`scheduled-drive-sync.md` already exercises, now applied to the queue's
rows instead of a hand-built batch file. It reports
`evaluated`/`refused`/`not found` counts and detail lines on stderr,
exactly as it already does.

## 3. Upload the candidate store back to Drive

Run this as long as steps 0-2 completed without error — this routine has no
notification or Slack step to gate on, so there's nothing to decouple from;
the upload is gated only on the local apply step succeeding, matching the
decoupling discipline `scheduled-drive-sync.md`'s Notes documents after the
real 2026-07-12 incident (a persisting step must never wait on a
notification step). Same resumable-upload recipe as
`scheduled-drive-sync.md`'s step 5 and `scan-slack-links.md`'s step 8,
overwriting the same well-known file in place — never a second
`candidates.db`-named file:

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

## Report

Report the `evaluated`/`refused`/`not found` counts from step 2, plus the
message_ids in each bucket (available from step 2's stdout/stderr). No Slack
posting — this matches the `notifications: {slack:false}` shape used on
other manually-fired-only triggers; the report is read from the trigger's
own run transcript by the interactive session that fired it, not pushed
anywhere. The interactive session uses this report to decide whether to
clear the local queue (`ingest queue-clear`) — only after seeing `refused`
and `not_found` are both empty for every row it expected to apply.

## Notes

- This routine, `scheduled-drive-sync.md`, and `scan-slack-links.md` all
  read-modify-write the same Drive-hosted `candidates.db`. Unlike the other
  two, this routine only ever runs when Jay explicitly fires it via
  `RemoteTrigger action:"run"` — never on a schedule — so an overlapping
  write is possible only if Jay fires it during the ~11-minute window the
  other two routines' runs might overlap each other. Accepted as a
  low-probability risk rather than adding locking/retry logic, consistent
  with `scan-slack-links.md`'s own Notes on the same tradeoff.
