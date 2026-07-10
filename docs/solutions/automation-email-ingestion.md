# automation-email-ingestion — Lesson

## Problem

Build the first slice of a 24/7 automation pipeline: turn newsletter email
into a durable, deduped backlog of candidate ideas. The obvious first
instinct — write a Python script with its own Gmail API client — turned out
to be solving the wrong problem.

## What worked

**Treating Gmail access as session-scoped, not script-owned, changed the
whole shape of the feature.** The Gmail MCP connector available in this
session is tied to an interactive Claude session's OAuth grant; a standalone
`uv run python` script has no way to hold or use that credential. Rather
than build a separate headless OAuth app (real scope: app registration,
token storage, refresh handling, secrets management), the "ingestion" step
was split into a deterministic half (a small sqlite-backed store, tested and
typed like any other code) and a judgment half (a literal, mechanically
precise markdown routine that any agent *with* Gmail access — this session,
or a future `CronCreate`-scheduled one — can execute). This is a pattern
worth reusing for every later pipeline stage that needs an external
credential this repo's own process can't hold: don't build a client, write a
routine.

**Asking Jay to confirm a proposed sender list, instead of asking him to
recall it from memory.** Searching his actual inbox for `unsubscribe`-bearing
mail from the last 30 days and filtering to obviously AI-relevant senders
produced a concrete list to confirm in one message, rather than an open
"what newsletters do you read" question. Faster, and lower-risk — the config
is git-ignored and trivially editable if any entry was wrong.

**Running the live proof against real inbox data, not fixtures.** 31 real
messages ingested, then the exact same ingestion re-run to independently
reconfirm idempotency against real data — this caught nothing new here, but
it's the same "prefer real verification" instinct that caught a genuine bug
on the prior feature (symbol-linked-rationale's HTTP endpoint), and it's
cheap enough to always do when the dependency (Gmail, in this case) is
actually available.

## What didn't work / had to be corrected

**First `agentalloy approve design` attempt failed** — the
`build_contracts_cover_tasks` gate counts task-list items across *every*
`docs/design/**/tasks.md` file in the repo, not just the current feature's.
A prior feature's leftover `tasks.md` (4 items, never cleaned up) combined
with this feature's own 6 pushed the required count to 10. Not a bug — the
gate is deliberately additive so a repo with multiple in-flight features
can't under-count — but worth knowing going in: **check for other design/
`tasks.md` files before assuming your own task count is what the gate
checks against.**

**Gmail's OAuth token had expired going in** — required stopping and asking
Jay to reconnect it (a browser flow only he can complete) rather than
guessing at a workaround. Real, unavoidable external blocker; the productive
move was pivoting to spec/design/scaffolding work that didn't depend on it
while he reconnected, so the blocker cost zero wall-clock time.

## Decisions worth keeping

- Small, single-writer local logs get `sqlite3` (stdlib), not this repo's
  DuckDB convention — DuckDB is for the analytical stores (skill corpus,
  code index), not every piece of local state.
- New tooling that isn't part of the `agentalloy` product package gets its
  own top-level directory (`automation/`), not a subpackage under
  `src/agentalloy/` — keeps `pyproject.toml`'s lint/typecheck/test scope
  additive and the product's own diff untouched.
- A routine that requires agent judgment (reading email content) should
  still pin down everything that *doesn't* need judgment — the query
  construction, the exact fields, the exact CLI call — so it's repeatable
  across whichever agent runs it, not just "figure out how to scan email."
