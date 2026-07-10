# Newsletter export — Apps Script setup

This deploys under your own Google account, not through Claude — nothing
here can be run or verified from this repo's tooling.

## Why this exists

The automation pipeline's scheduled cloud routines can't reach Gmail
directly (Gmail isn't an available MCP connector for routines, unlike
Drive/Calendar). This script runs under your own account's native Gmail
access and writes matching newsletter content to a Drive file the routine
*can* read. See `docs/spec-contracts/automation-drive-sync.spec.md` for
the full context.

## Setup

1. Go to [script.google.com](https://script.google.com) and create a new
   project.
2. Delete the default `Code.gs` content and paste in
   `newsletter-export.gs` from this directory.
3. Edit `SENDER_ALLOWLIST` at the top of the script to match your real
   newsletter senders — this is a separate copy from the repo's
   `automation/config/sources.yaml` (Apps Script can't read local repo
   files), so keep the two in sync by hand if you change one.
4. Run `exportNewsletters` once manually (▶ button) to trigger the OAuth
   consent screen — approve Gmail read access and Drive access. This is
   your own consent; nothing in this repo or session can do it for you.
5. Set up a time-based trigger: in the Apps Script editor, click the clock
   icon (Triggers) → **Add Trigger** → function `exportNewsletters`, event
   source **Time-driven**, pick an interval (hourly or a few times a day is
   reasonable given the routine's own minimum 1-hour schedule interval).

## What it does each run

- Searches Gmail for messages from your allowlisted senders that aren't
  already labeled `agentalloy-automation-exported`.
- Appends one JSON line per matching message to
  `agentalloy-automation-newsletter-export.jsonl` in your Drive (creating
  it on first run).
- Labels each processed message so it isn't re-exported next run.

## Field contract

Every exported line must have exactly these six fields, matching what
`automation/cli.py`'s `ingest import-jsonl` command requires:
`message_id`, `thread_id`, `source`, `subject`, `received_at`, `snippet`.
If you modify the script, keep this contract — the import side validates
these exact field names and silently skips any line missing one.
