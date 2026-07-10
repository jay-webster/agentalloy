# Routine: scan-newsletters

Followed by an agent with Gmail MCP access (an interactive Claude Code
session today; potentially a `CronCreate`-scheduled agent later). Every step
below is literal — no judgment calls beyond reading matched email content to
fill in the extracted fields.

## 1. Load the allowlist

Read `automation/config/sources.yaml` (a YAML list of sender
addresses/domains — see `automation/config.py`'s `load_sources`). If it
doesn't exist yet, copy `automation/config/sources.example.yaml` to
`automation/config/sources.yaml` and fill in real senders before continuing.

## 2. Build the Gmail query

Join every allowlist entry as `from:<entry>`, `OR`-combined, restricted to
the inbox:

```
in:inbox {from:sender-one from:sender-two from:sender-three ...}
```

Call the Gmail `search_threads` tool with that query string.

## 3. Extract fields per matching thread

For each thread returned, call `get_thread` (or use the fields already
present from `search_threads` if sufficient) and extract:

| Candidate field | Source |
|---|---|
| `message_id` | the message's id within the thread |
| `thread_id` | the thread's id |
| `source` | the sender address |
| `subject` | the message subject |
| `received_at` | the message's date header, ISO 8601 |
| `snippet` | the message snippet, or a short (1-2 sentence) summary if the snippet alone doesn't convey what the email is about |
| `ingested_at` | the current time, ISO 8601, at the moment this routine runs |

If a thread has multiple messages from allowlisted senders, extract one
candidate per message, not one per thread.

## 4. Record each candidate

For every extracted candidate, run:

```
uv run python -m automation.cli ingest add \
  --message-id "<message_id>" \
  --thread-id "<thread_id>" \
  --source "<source>" \
  --subject "<subject>" \
  --received-at "<received_at>" \
  --snippet "<snippet>" \
  --ingested-at "<ingested_at>"
```

## 5. Idempotency

Re-running this routine over previously-seen mail is safe by design —
`ingest add` no-ops on a `message_id` it already has. No "have I seen this
before" check is needed before running the query; let the store handle it.

## 6. Report

After the routine completes, run `uv run python -m automation.cli ingest
list --status new` and report the count and a one-line summary of what was
found (or that nothing matched).
