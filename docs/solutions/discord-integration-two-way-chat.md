# Discord Integration — Two-Way Chat

## Decision

Two-way Discord chat for interactive and background Claude Code sessions
already exists — no new infrastructure was built for AC6–AC8. The
installed `plugin:discord:discord` MCP tools (`reply`, `fetch_messages`,
`react`, `edit_message`) already provide it, gated by Jay's own
`/discord:access` skill, which he runs himself (satisfies AC8: no
credential handling by Claude).

## Usage pattern (interactive/background sessions)

1. Post the question: `reply(chat_id, "question text")`, optionally with
   `reply_to` set to thread it under an earlier message.
2. Poll for Jay's answer: `fetch_messages(channel, limit=N)`, filtering for
   a message from Jay with a timestamp newer than the question's own
   `ts`. Discord's search API isn't exposed to bots, so this is
   fetch-recent-and-filter, not a targeted lookup.
3. Loop step 2 with a short wait between polls until a matching message
   appears (or a reasonable timeout is reached).

This is the whole mechanism — no queue, no webhook listener, no new
tooling. A future session picking this up shouldn't need to re-derive it.

## Explicitly out of scope: CCR one-shot `RemoteTrigger` runs

This mechanism does **not** cover unattended `RemoteTrigger` scheduled
routines (e.g. `scheduled-drive-sync.md`), and that is a decision, not an
oversight:

- Whether a Discord-type MCP connector can even be attached to a
  `RemoteTrigger` job_config at all is unverified from inside this repo —
  it depends on the CCR platform's supported connector types, not on
  anything checkable via `grep`/`Read`.
- Even if it can, a one-shot, non-resumable run has nowhere to
  block-and-wait for a reply across its own execution the way an
  interactive session can.

If this is ever revisited, the starting question is simply "does the
`RemoteTrigger` platform support a Discord connector type," checked via
`RemoteTrigger action=get` on a trigger that has one attached — the same
way the Drive-connector gap was confirmed (see
[[drive-sync-blockers]]). Wiring a Discord connector into a live trigger's
`allowed_tools`/`mcp_connections` would itself be a standing-configuration
change requiring Jay's explicit confirmation before applying, per the same
precedent.

## Current fallback for the unattended case

The `evaluate()` `needs_review` verdict (shipped in
newsletter-pipeline-efficiency) is the existing mechanism for "ask Jay
something, later" when no session is available to block on an answer —
routed to Jay asynchronously via the digest/report, not through a live
two-way exchange. This remains the fallback until/unless the CCR-side gap
above is resolved.
