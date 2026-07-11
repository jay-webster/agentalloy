# Automation Discord Notify — Spec

> **Scope in a sentence.** After each scheduled run, produce a deterministic
> digest of what happened and post it to a Discord channel via an incoming
> webhook — closing the "results are only visible by checking manually" gap
> left open since the routine went live.

> **Location note.** At runtime the SDD spec phase writes the spec to
> `docs/spec/automation-discord-notify.md`, git-ignored. This file is the
> committed, reviewable copy.

## Context

The scheduled routine (created 2026-07-11, `trig_015i5taDUbLn7wHfbhb6BT5V`)
runs unattended, but nothing surfaces its results — Jay would have to check
the routine's run history or inspect the Drive-hosted db manually to know
anything happened, defeating part of the point of automation. The original
pipeline vision named Discord as the notification channel from the start.

Discord access in this environment is a local bot-token plugin
(`mcp__plugin_discord_discord__*`), not a claude.ai MCP connector — it is
not available to a `RemoteTrigger` routine's cloud sandbox, the same
category of gap as Gmail. Unlike Gmail, there's a direct fix: Discord's
**incoming webhooks** are a plain HTTPS endpoint any HTTP client can POST
JSON to — no OAuth, no connector, no bot infrastructure. A routine's `Bash`
tool can `curl` a webhook directly. This sidesteps the connector-
availability problem entirely rather than requiring a bridge like the
Gmail/Drive/Apps-Script chain did.

## Assumptions (correct these before design)

- **The webhook URL is a secret Jay provides and owns** — created in his
  own Discord server, given directly to this session, embedded only in the
  routine's own configuration (via `RemoteTrigger update`), never committed
  to the repo. Configuring a webhook integration is an explicit-permission
  action per this session's standing rules — confirmed with Jay before the
  routine's configuration is actually updated, not assumed from the general
  "let's tackle these in order" direction.
- **The digest is deterministic, testable content; the delivery (`curl`) is
  a routine-prompt instruction, not new Python.** Same split as every prior
  slice: build the part that can be tested, document the part that can't.
- **Scope is "this run's results," not full store state.** A digest command
  filtered by `evaluated_at >= <a timestamp>` naturally captures "what this
  run just decided" without needing new tracking state — the routine
  captures the current time before its evaluation step and passes it to
  the digest command after.
- **`accept` and `needs_review` verdicts get full detail** (they need
  attention or represent real decisions); `reject` gets a bare count (no
  action needed, would just add noise). Flagged (injection-guard) hits get
  a brief count-only mention if any occurred, informational only — `accept`
  is already structurally blocked for flagged candidates by slice 3, so
  there's nothing actionable to add beyond noting it happened.
- **No message-length safeguard beyond what's proportionate to expected
  volume** (a handful of newsletters/day, per the original design
  assumption, confirmed roughly accurate by the real Apps Script run). If
  actual volume grows enough to risk Discord's message-length limits,
  that's a future problem, not solved speculatively here.

## What

**Digest command.** `automation/cli.py`: `ingest report --since <ISO8601
timestamp>` — queries candidates with `evaluated_at >= since`, prints a
formatted digest: total evaluated count; verdict breakdown (accept /
reject / needs_review counts); full detail (message_id, subject, source,
rationale) for every `accept` and `needs_review` candidate; a bare count
for `reject`; a one-line flagged-count mention if any flagged candidates
were evaluated this run. No `accept`/`needs_review` candidates and no
flagged ones → a short "nothing needs your attention" style line, not a
wall of zeros.

**Routine update.** `scheduled-drive-sync.md` gains a final step: capture
the current UTC time before the evaluation step (step 4), run `ingest
report --since <captured time>` after it completes, then `curl` the
resulting text to the Discord webhook URL (provided in the routine's own
configuration, not the repo) as a JSON payload, before or alongside the
existing Drive upload step.

**Live routine update.** Once Jay provides the webhook URL, the actual
`RemoteTrigger` routine is updated (via `RemoteTrigger action: update`) to
include the new step and the webhook URL — a real, standing-configuration
change requiring explicit confirmation at the time, per this session's
rules on webhook/integration changes.

## Acceptance Criteria

1. **`report` filters correctly by `evaluated_at`.** Only candidates
   evaluated at or after the given timestamp appear; earlier-evaluated
   candidates (e.g. tonight's original 39) do not. Verifiable by a unit
   test seeding candidates with different `evaluated_at` values.
2. **Verdict-specific detail level is correct.** `accept`/`needs_review`
   candidates in the digest show message_id, subject, source, and
   rationale; `reject` shows only in the count, not itemized. Verifiable
   by a unit test with one of each verdict.
3. **Empty-window output is a short positive statement, not a wall of
   zeros.** `report --since <a time after everything>` (nothing evaluated
   in that window) produces a single-line "nothing to report" style
   message, not an empty/awkward digest. Verifiable by a unit test.
4. **Flagged mention is count-only and conditional.** A digest covering a
   window with N flagged candidates includes a one-line mention of N; a
   window with zero flagged candidates omits the line entirely. Verifiable
   by two unit tests (present and absent cases).
5. **No product code touched, no new dependency, no LLM call.** Same bar
   as every prior slice — zero diff under `src/agentalloy/`; `report` uses
   only stdlib.
6. **Live proof of the testable half.** `ingest report` run against the
   real production store (39 real candidates, all evaluated last night)
   with a `--since` timestamp chosen to include some of them, output shown
   as evidence the formatting is correct against real data.
7. **Webhook delivery is verified live, with explicit confirmation before
   the routine's standing configuration changes.** Once Jay supplies a
   webhook URL and confirms, a real `curl` POST of real digest output is
   sent and its arrival in Discord is confirmed with Jay — this is the one
   piece of this slice that touches a live external system and needs his
   explicit go-ahead, not just the general "tackle these in order"
   direction.

## Out of Scope

- **Any other notification channel** (email, SMS, push) — Discord only,
  matching the original pipeline vision.
- **Two-way interaction** (Jay replying in Discord to accept/reject a
  candidate from the channel) — this slice is send-only.
- **Message-length truncation/pagination** for very large digests — not
  needed at expected volume, see Assumptions.
- **Changing what the evaluator does** — this slice only reports on
  verdicts already being recorded; the two-lens-framework question from
  slice 2 is untouched.
- **Any cloud or paid-LLM call from the report command itself.**

## Design surface (hand-off to the design phase)

- **Digest text format** — plain text (simplest, works with a bare Discord
  webhook JSON payload's `content` field) vs. Discord's richer "embed"
  format (more visually structured, more payload complexity). Given no AC
  requires embeds, lean toward plain text unless the design phase finds a
  concrete reason not to.
- **Where the "since" timestamp gets captured** — the routine prompt
  capturing it via `date -u` at the right point in its own sequence, not
  new code (this is orchestration, not logic the store needs to own).
