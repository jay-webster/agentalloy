# automation-integrator-intake — Test Plan

## Test Cases

### Task 1 — pure functions

- **T1.1 (AC4).** `slugify("OpenAI Is Building an AI Superapp",
  "19f4c1c888d64b0d")` returns a lowercase, hyphenated slug ending in
  `-19f4c1c8` (or equivalent 8-char prefix), deterministic across calls.
- **T1.2 (AC4).** Two candidates with identical subjects but different
  `message_id`s produce different slugs.
- **T1.3 (AC3).** `render_draft(candidate, slug)` output contains the
  candidate's `subject`, `source`, `rationale`, `snippet`, and the exact
  string `agentalloy contract init --phase spec --slug {slug}`.

### Task 2 — store

- **T2.1 (AC1).** `integrate()` on a candidate with `verdict=None`
  (never evaluated) raises `NotAcceptedError`; no file written, no row
  change.
- **T2.2 (AC1).** Same, for `verdict="reject"` and `verdict="needs_review"`
  (two separate cases).
- **T2.3 (AC2).** `integrate()` on an `accept` candidate, then modify the
  written draft file's contents directly, then `integrate()` again — second
  call's return has `already_existed=True`, and the file's contents are
  unchanged from the modification (proves no overwrite).
- **T2.4 (AC5).** `integrate("does-not-exist")` raises (mirrors the
  missing-candidate shape used elsewhere in this module).
- **T2.5.** `integrate()` on a fresh `accept` candidate: the row's
  `integrated_at`/`integration_slug` are set after the call, `None` before.

### Task 3 — CLI

- **T3.1 (AC1).** `ingest integrate <id>` on a non-accept candidate exits
  non-zero with a message naming the actual verdict.
- **T3.2 (AC2).** `ingest integrate <id>` run twice on an accept candidate:
  second run's output says "already integrated," draft file untouched.

### Task 4 — live proof

- **T4.1 (AC7).** Real `add()` → `evaluate(accept)` → `integrate()` via the
  CLI; draft file's actual contents shown as evidence. Second `integrate()`
  call confirms idempotency against the real filesystem. Test candidate row
  and draft file deleted afterward.
