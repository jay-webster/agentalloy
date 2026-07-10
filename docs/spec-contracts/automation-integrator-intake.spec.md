# Automation Integrator Intake — Spec

> **Scope in a sentence.** On an `accept` verdict, generate a draft SDD
> intake artifact primed from the candidate's content — the hand-off point
> where the pipeline stops and a human-supervised SDD cycle takes over, not
> where autonomous code changes begin.

> **Location note.** At runtime the SDD spec phase writes the spec to
> `docs/spec/automation-integrator-intake.md`, git-ignored. This file is the
> committed, reviewable copy.

## Context

Slice 2 (evaluator) records a verdict; nothing yet acts on `accept`. The
pipeline's original target shape describes the integrator as running
agentalloy's *full* SDD lifecycle unsupervised and opening a PR — a real
scope jump from everything shipped so far (closer to a second orchestrator
than a single slice), and there is currently no real `accept` verdict to
build or test it against (all 31 real candidates evaluated so far landed on
`reject`/`needs_review`). Per explicit direction, tonight's integrator slice
is deliberately narrower: stop at intake hand-off, leave spec→design→build→
qa→ship to a human (or a human-supervised session), same as every other
piece of SDD work done tonight.

This also follows directly from slice 3's sequencing decision (harden
before autonomy) — building toward autonomous execution incrementally,
proving each step before the next one increases blast radius, rather than
jumping straight to "read a verdict, write code, open a PR."

## Assumptions (correct these before design)

- **Only `accept` verdicts are integratable.** `reject`/`needs_review`
  candidates cannot be integrated — attempting it is a clear, immediate
  refusal, not a state the deterministic code needs to guard against
  happening silently.
- **A flagged candidate can never have `verdict="accept"`** — slice 3's
  `evaluate()` already guarantees this structurally. This slice does not
  re-implement that check; it relies on the existing guarantee.
- **The draft is a starting point, not a real spec.** It does not, and must
  not, satisfy the SDD spec phase's actual exit gates (`## Acceptance
  Criteria`, `## Out of Scope` sections with real content) — it primes a
  human to write those, quoting the candidate's source material so they
  don't have to go re-find it.
- **Idempotent means "never overwrite,"** not "regenerate every time." Once
  a draft exists, a human may already be editing it — re-running the
  integrator on the same candidate must be a safe no-op that reports what
  already happened, never a silent overwrite of in-progress human work.
- **The draft location is deliberately separate from `docs/spec/`** (the
  live SDD runtime path) — writing into `docs/spec/` directly could
  silently collide with or overwrite spec work already in progress for an
  unrelated task.

## What

**Storage.** Two new nullable columns on `candidates`: `integrated_at`
(timestamp, `NULL` until integrated) and `integration_slug` (text, the
generated slug, `NULL` until integrated). Additive migration, same pattern
as slices 2-3.

**Slug generation.** Deterministic: a slugified prefix of the candidate's
subject plus a short suffix from its `message_id`, guaranteeing uniqueness
without needing collision-detection logic.

**CLI.** `ingest integrate <message_id>`:
- Refuses (clear message, non-zero exit, no write) if the candidate's
  verdict isn't `accept`.
- No-ops (reports the existing draft's path, does not touch the file) if
  already integrated.
- Otherwise: generates the slug, writes a draft file to
  `automation/intake-drafts/<slug>.md` templated from the candidate's
  stored fields (subject, source, rationale, snippet, received date) plus a
  footer naming the exact next command
  (`agentalloy contract init --phase spec --slug <slug>`), and records
  `integrated_at`/`integration_slug` on the row.

**Live proof.** Since there is no real `accept` candidate yet, construct
one deliberately (clearly labeled as proof data, same approach slice 3 used
for its adversarial check), run it through the real `add()` → `evaluate()`
→ `integrate()` path, inspect the generated draft file, then clean up the
test row and file afterward — not left in the production store or repo.

## Acceptance Criteria

1. **Only `accept` candidates can be integrated.** `integrate()` on a
   `reject`/`needs_review`/un-evaluated candidate refuses with a clear
   error, writes nothing. Verifiable by unit tests covering all three
   non-accept states.
2. **Idempotent, never overwrites.** Calling `integrate()` twice on the
   same candidate: the second call reports the existing draft's path and
   does not modify the draft file's contents or the row's
   `integrated_at`/`integration_slug`. Verifiable by a unit test that edits
   the draft file between the two calls and asserts the edit survives.
3. **Draft content is templated from stored fields, not LLM-generated.**
   The draft file contains the candidate's subject, source, rationale, and
   snippet verbatim, plus the exact next-step command naming the generated
   slug. Verifiable by a unit test asserting each field's presence in the
   written file.
4. **Slug is deterministic and unique-by-construction.** The same candidate
   always generates the same slug; two different candidates with identical
   subjects generate different slugs (via the message_id suffix).
   Verifiable by unit tests.
5. **Missing candidate is a reported no-op**, matching `mark`/`evaluate`'s
   existing missing-id behavior. Verifiable by a unit test.
6. **No product code touched, no new dependency, no LLM call in shipped
   code.** Same bar as prior slices — zero diff under `src/agentalloy/`;
   grep for `lm_client`/`embed` in the new/touched code returns nothing.
7. **Live proof, real path.** A deliberately constructed `accept` candidate
   is run through the real `add()` → `evaluate()` → `integrate()` path via
   the CLI in this session; the generated draft file's real contents are
   shown as evidence, then the test candidate and draft file are removed
   (not left as production artifacts).

## Out of Scope

- **Running any part of the actual SDD lifecycle** (spec, design, build,
  qa, ship) on behalf of the accepted candidate — the draft is the hand-off
  point; everything past it is a later slice, explicitly deferred pending
  more real `accept` data and further deliberate scoping (matching slice
  3's incremental-blast-radius sequencing).
- **Opening any PR against agentalloy** on behalf of an accepted candidate.
- **Notifying Jay** that a draft is ready (Discord/push wiring still
  unresolved).
- **Re-evaluating any of the 31 real candidates already recorded** as
  `reject`/`needs_review` to manufacture live-proof data — the live proof
  uses a clearly-labeled synthetic candidate instead, consistent with not
  corrupting real evaluation history for demo purposes.
- **Any cloud or paid-LLM call from the store/CLI code itself.**

## Design surface (hand-off to the design phase)

- **Draft file format** — how much structure to impose (a bare quoting of
  fields vs. something closer to the spec-contract template's headings) —
  balance "primes a human effectively" against "don't pretend to be a real
  spec."
- **Slug collision handling** — the message_id suffix approach should make
  collisions effectively impossible; confirm this is sufficient rather than
  adding retry/uniqueness-check logic that isn't needed.
