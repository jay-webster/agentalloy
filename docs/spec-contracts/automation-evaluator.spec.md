# Automation Evaluator — Spec

> **Scope in a sentence.** Given a candidate sitting at `status="new"` in
> slice 1's store, record a verdict (accept / reject / needs Jay's judgment)
> and a short rationale — the second slice of the automation pipeline,
> stopping short of actually building anything.

> **Location note.** At runtime the SDD spec phase writes the spec to
> `docs/spec/automation-evaluator.md`, git-ignored. This file is the
> committed, reviewable copy.

## Context

Slice 1 (`automation-email-ingestion`, shipped as PR #1) produces a durable
backlog of candidates with `status="new"`. Nothing yet decides which of
those are worth acting on. This slice closes that gap using the same split
that worked for ingestion: a deterministic, tested component (verdict
storage + CLI) plus an agent-executed routine (the actual judgment call,
which cannot be deterministic — "is this worth integrating into agentalloy"
is exactly the kind of call this session already made three times tonight
for the cookbook notebook, the CLAUDE.md article, and the Agent Skills repo,
each requiring reading real content and reasoning about fit, not a
classifier).

Per the pipeline's target shape (project memory) and the standing model-
upgrade principle, "worth acting on" has two independent lenses a candidate
should be checked against:

1. **Feature fit** — does this suggest a capability agentalloy doesn't have.
2. **Local-model-replacement fit** — could this replace/improve one of
   agentalloy's own local models (embed model, reranker), independent of
   whether it suggests any new *feature*.

A third outcome — genuinely ambiguous, needs Jay's judgment — is real and
distinct from "reject." Collapsing it into reject would silently lose good
ideas that just need a human call; collapsing it into accept would trigger
unwanted autonomous work. This slice records that third outcome but does
not yet act on it (see Out of Scope — notification is a separate slice).

## Assumptions (correct these before design)

- Verdicts are **agent-recorded, not agentalloy-computed** — same
  "deterministic where possible, explicit where not" split as the ingestion
  routine. The store/CLI never calls an LLM; the routine that decides the
  verdict does, by virtue of being agent-executed.
- A candidate can be **re-evaluated** (verdict overwritten) — unlike
  ingestion's dedup-by-message_id, there's no reason to forbid updating a
  stale verdict later (e.g. agentalloy's scope changes). Not idempotent in
  the "no-op on repeat" sense; idempotent in the "same inputs, same
  resulting row" sense.
- **Manual feed-in already works, with zero new code.** Slice 1's `ingest
  add` CLI already accepts arbitrary field values — a candidate that didn't
  come from Gmail (a pasted idea, a synthetic `message_id`) flows through
  this slice's evaluation routine identically to an inbox-sourced one. This
  spec does not add a separate manual-entry path; it's already covered.
- This slice decides; it does not act. "Accept" does not trigger a build —
  see Out of Scope.

## What

**Storage.** Two new nullable columns on the existing `candidates` table:
`verdict` (`accept` | `reject` | `needs_review`, `NULL` until evaluated) and
`rationale` (free text, `NULL` until evaluated). Additive migration — no
existing column changes, no data loss for slice 1's already-ingested rows.

**CLI.** `ingest evaluate <message_id> --verdict {accept,reject,needs_review}
--rationale "..."` — sets `verdict`, `rationale`, moves `status` from `new`
to `evaluated`, sets `evaluated_at`. Re-running against an already-evaluated
`message_id` overwrites the prior verdict (not an error, not a no-op).

**Routine.** `automation/routines/evaluate-candidate.md` — for each
`status="new"` candidate: fetch the full message body (best-effort, via
Gmail `get_message` when `message_id` looks like a real Gmail id) for more
signal than the stored snippet alone provides, assess it against both
lenses above, then record the verdict via the CLI with a rationale that
names *which* lens (or neither) drove the call.

**Live proof.** This session, once built, the routine is run for real
against slice 1's 31 already-ingested candidates, producing real verdicts
and rationale — not a fixture-only test run.

## Acceptance Criteria

1. **Schema migration is additive and non-destructive.** `verdict` and
   `rationale` columns are added via a migration that is safe to run
   against a database slice 1 already created (existing rows keep their
   data, new columns are `NULL`). Verifiable by a test that seeds a slice-1-
   shaped row, runs the migration, and asserts the row's original columns
   are unchanged.
2. **Evaluating a candidate sets verdict, rationale, status, and
   evaluated_at together.** Verifiable by a unit test asserting all four
   fields after one `evaluate` call.
3. **Re-evaluation overwrites, not errors or duplicates.** Calling
   `evaluate` twice on the same `message_id` with different verdicts leaves
   exactly one row reflecting the second call. Verifiable by a unit test.
4. **Evaluating a nonexistent `message_id` is a reported no-op**, matching
   `mark`'s existing missing-id behavior — not an unhandled exception.
   Verifiable by a unit test.
5. **Only valid verdict values are accepted** (`accept` / `reject` /
   `needs_review`); anything else is rejected with a clear error before
   touching the database. Verifiable by a unit test.
6. **`list` can filter/display verdict.** `ingest list --status evaluated`
   shows the verdict and rationale alongside the existing fields. Verifiable
   by a unit test.
7. **No product code touched, no new dependency, no LLM call in shipped
   code.** Same bar as slice 1 — zero diff under `src/agentalloy/`; grep for
   `lm_client`/`embed` in the new/touched store and CLI code returns
   nothing.
8. **Live end-to-end proof.** The routine is run for real against slice 1's
   already-ingested candidates in this session; resulting verdicts and
   rationale are shown via `ingest list --status evaluated`, not asserted
   from fixtures alone.

## Out of Scope

- **Acting on an "accept" verdict** (running agentalloy's SDD lifecycle,
  opening a PR) — a later slice, gated on this one existing first.
- **Notifying Jay about `needs_review` candidates** (Discord/push) —
  routing config is still unresolved (see project memory); this slice only
  makes `needs_review` a queryable state (`ingest list --status evaluated`
  plus checking the `verdict` column), not a proactive alert.
- **A dedicated manual feed-in CLI verb** — already covered by slice 1's
  `ingest add`, see Assumptions.
- **Any cloud or paid-LLM call from the store/CLI code itself.**
- **Confidence scoring, ranking, or batching multiple candidates into one
  verdict call.** One candidate, one verdict, one rationale — the simplest
  shape that's still real.

## Design surface (hand-off to the design phase)

- **Migration mechanism.** `sqlite3`'s `ALTER TABLE ADD COLUMN` is not
  idempotent by default (`ADD COLUMN` errors if the column already exists,
  unlike DuckDB's `CREATE TABLE IF NOT EXISTS` this repo otherwise relies
  on) — decide the guard (check `PRAGMA table_info` first, or catch the
  specific `OperationalError` and treat it as already-applied).
- **Verdict value validation** — an application-level check (a small
  allowed-set constant) vs. a `CHECK` constraint in the schema itself. Given
  sqlite's `CHECK` constraints are enforced, either is viable; pick based on
  which gives a clearer error message path for AC5.
- **Routine's Gmail body-fetch fallback** — what exactly counts as "looks
  like a real Gmail id" for the best-effort `get_message` call, given
  manually-fed candidates (Assumptions) may have synthetic `message_id`
  values that would 404 against Gmail. Should not hard-fail the routine
  either way.
