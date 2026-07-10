# Automation Email Ingestion — Spec

> **Scope in a sentence.** Build a durable, deduped store of "candidate AI
> innovations" found in Jay's inbox, plus a documented scan routine an agent
> follows to populate it — the first slice of the 24/7 automation pipeline,
> intentionally stopping short of evaluation or auto-build.

> **Location note.** At runtime the SDD spec phase writes the spec to
> `docs/spec/automation-email-ingestion.md`, git-ignored. This file is the
> committed, reviewable copy.

## Context

The automation pipeline's target shape (per prior session, see project
memory) is: scan inbox → evaluate against agentalloy → if worthwhile, run
agentalloy's own SDD lifecycle and open a PR → notify Jay. That's too much
for one slice. This spec covers only the first stage: turning "stuff in
Gmail" into a structured, queryable backlog of candidates, reliably and
without re-processing the same email twice.

A key architectural fact discovered while scoping this: Gmail access in this
environment is a Claude-side MCP connector tied to *this interactive
session's* OAuth grant — not a credential a standalone Python script can
hold and call unattended. Building a headless Gmail API client (its own
OAuth app registration, token storage, refresh handling) is real scope this
slice deliberately defers. Instead, "ingestion" is modeled as an **agent
routine**: a precise, mechanical set of instructions (Gmail query, extraction
fields, CLI call to record the result) that any agent with Gmail MCP access —
this session tonight, or a scheduled Claude Code agent later via
`CronCreate` — can follow. The code this slice ships is the deterministic
half: the store the routine writes into.

## Assumptions (correct these before design)

- "AI innovation newsletter" is defined by an explicit sender/domain
  allowlist Jay maintains, not inferred by classifying arbitrary inbox
  content — consistent with agentalloy's own preference for deterministic,
  configured behavior over guessing (see working-style memory).
- One candidate = one Gmail message. Threads with multiple relevant messages
  produce multiple candidates (dedup is per message_id, not per thread).
- This slice does not decide whether a candidate is worth building — it only
  makes candidates durably visible for that later step (the manual feed-in
  evaluator, from the options discussed but not yet built) to consume.
- Scheduling the routine to actually run unattended (`CronCreate`) is
  deliberately **not** part of this slice — see Out of Scope.

## What

**Store.** A new local, git-ignored SQLite database tracking one row per
ingested Gmail message: `message_id` (unique key), `thread_id`, `source`
(sender address/domain), `subject`, `received_at`, `snippet`, `status`
(`new` | `evaluated` | `accepted` | `rejected`), `ingested_at`. Re-ingesting
an already-seen `message_id` is a no-op, not a duplicate row or an error.

**Config.** A tracked example allowlist
(`automation/config/sources.example.yaml`) plus a git-ignored real one
(`automation/config/sources.yaml`, copied from the example and edited by
Jay) listing sender addresses/domains that count as newsletter sources. The
routine's Gmail query is built from this list.

**CLI.** `uv run python -m automation.cli ingest add ...` (record one
candidate; idempotent) and `uv run python -m automation.cli ingest list
[--status new]` (inspect the backlog).

**Routine.** `automation/routines/scan-newsletters.md` — instructions
precise enough for an agent to execute mechanically: which Gmail query to
run against the configured allowlist, which fields to extract per matching
message, and the exact CLI invocation to record each one.

**Live proof.** Once Gmail access is available this session, the routine is
run for real against Jay's actual inbox (not fixture data) and the resulting
store contents are shown as evidence the loop works end to end.

## Acceptance Criteria

1. **Idempotent ingestion.** Adding the same `message_id` twice leaves
   exactly one row, with no error. Verifiable by a unit test calling `add`
   twice and asserting `list` returns one row.
2. **New candidates land with `status = new`.** Verifiable by a unit test.
3. **List filters by status.** `list(status="new")` excludes rows with other
   statuses. Verifiable by a unit test seeding mixed-status rows.
4. **Status is updatable** (`mark` moves a candidate from `new` to
   `evaluated`/`accepted`/`rejected`), and updating a nonexistent
   `message_id` is a reported no-op, not an unhandled exception. Verifiable
   by unit tests for both the happy path and the missing-id path.
5. **Config-driven, not hardcoded.** The allowlist is read from
   `automation/config/sources.yaml` (falling back to a clear error naming the
   example file if absent) — no sender list literal in the routine or CLI
   code. Verifiable by code inspection plus a test pointing the loader at a
   fixture config.
6. **No product code touched.** Zero diff under `src/agentalloy/`; this
   ships entirely under a new top-level `automation/` package (plus minimal,
   additive `pyproject.toml` tooling-scope changes to lint/typecheck/test the
   new package — no behavior change to the existing `agentalloy` package).
7. **Deterministic — no LLM call anywhere in the store or CLI.** Verifiable
   by code inspection (no embed/LM client import in `automation/store.py` or
   `automation/cli.py`).
8. **Live end-to-end proof.** After Gmail reconnection, running the scan
   routine once against Jay's real inbox produces at least one real row in
   the store (or a documented zero-match result if nothing matches the
   configured allowlist), shown via `ingest list` output in this session —
   not asserted from fixtures alone.

## Out of Scope

- **Evaluating candidates** (does this belong in agentalloy) — the next
  slice.
- **Auto-build / PR opening** — a later slice, gated on evaluation existing
  first.
- **Discord notification wiring** — routing config for this project is still
  unresolved (see project memory); not blocking this slice.
- **Unattended/headless Gmail access** (a script-owned OAuth app + stored
  refresh token, independent of any interactive Claude session). This slice
  proves the routine works when *an agent with Gmail access* runs it; making
  that run happen automatically on a schedule is a separate, later decision
  (most likely: `CronCreate` a scheduled Claude Code agent that has Gmail MCP
  access and runs this same routine — not a bespoke Python API client).
- **Any cloud or paid-LLM call from the store/CLI code itself.**

## Design surface (hand-off to the design phase)

- **Store engine.** Plain `sqlite3` (stdlib, zero new dependency) vs. reusing
  `duckdb` (already a project dependency, used elsewhere in this repo).
  Given this is a small single-writer local log, not an analytical store,
  lean toward the simplest option unless there's a concrete reason to match
  the rest of the codebase's DuckDB convention.
- **Config loading.** Reuse whatever YAML loader the rest of the repo already
  depends on (check `pyproject.toml`) rather than adding a new one.
- **CLI framework.** `argparse` (stdlib, matches `agentalloy`'s own CLI) vs.
  `click` (already a transitive dependency per `.venv` inspection). Prefer
  whichever needs zero new dependency additions.
- **Where the gitignored data file and real config live** — inside a
  `.automation/` directory at repo root (mirroring the existing `.agentalloy/`
  convention) vs. under `automation/data/`. Pick one and update `.gitignore`.

---

*Next step per the SDD spec phase: present this spec, get explicit approval, then
`agentalloy approve spec` to seed the design work-item.*
