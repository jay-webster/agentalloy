# Routine: scan-discord-links

Followed by an agent with Discord MCP access (`plugin:discord:discord`) — an
interactive Claude Code session today; potentially a `CronCreate`-scheduled
agent later. Every step below is literal — no judgment calls beyond reading
matched message content to fill in the extracted fields.

## 1. Get the cursor

```
uv run python -m automation.cli ingest discord-cursor get
```

Prints the last-processed Discord message ID (a snowflake), or nothing if
this is the first run. Keep this value; it's the low-water mark for step 3.

## 2. Fetch messages

Call the Discord `fetch_messages` tool for the channel Jay uses for this
(the same channel used for two-way chat with him today — no separate config
file). A `limit` of 100 is enough to cover any reasonable gap between scans.

## 3. Filter to Jay's messages newer than the cursor

Keep only messages authored by Jay himself (never Claude's own `reply()`
output, never anyone else's messages) whose message ID is greater than the
cursor from step 1 (or all of Jay's messages, if no cursor is set yet).
Compare IDs as integers — Discord snowflakes are numeric strings.

If no messages remain after filtering, skip to step 6 and report zero
activity — do not advance the cursor (there's nothing new to advance it to).

## 4. Extract links per message

For each remaining message, in ascending message-ID order:

1. Write the message's content to a temp file.
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

For every URL extracted in step 4 (up to the per-run cap), run:

```
uv run python -m automation.cli ingest add-url \
  --url "<url>" \
  --subject "<first ~60 chars of the message that contained it>" \
  --received-at "<message timestamp, ISO 8601>" \
  --source discord
```

## 6. Advance the cursor

Only after every message in this run has been processed without error,
advance the cursor to the newest message ID seen this run:

```
uv run python -m automation.cli ingest discord-cursor set --message-id "<newest message ID>"
```

Advancing only on full success means a mid-run failure (e.g. a store I/O
error) leaves the cursor where it was, so a retry reprocesses from the same
point rather than silently skipping a message — `add-url`'s dedup makes that
retry safe (already-added URLs no-op rather than duplicate).

## 7. Report

Report: candidates added, already-present skips, per-message cap skips
(URLs beyond the 5-per-message cap), and per-run cap skips (URLs beyond the
20-per-run cap after it was reached).
