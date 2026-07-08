---
phase: build
task_slug: 02-ship-gate-and-codify-prose
route: full
domain_tags:
  - workflow-gates
scope:
  touches:
    - "src/agentalloy/_packs/sdd/sdd-deliver-and-ship.yaml"
    - "tests/**"
  avoids:
    - "src/agentalloy/signals/**"
    - "src/agentalloy/api/**"
success_criteria: []
related_contracts: []
created_at: 2026-07-08T00:00:00Z
---

# 02-ship-gate-and-codify-prose

## Task

Wire Piece 1 into the shipped ship workflow skill. First the D2 spike: confirm
the ship→intake reset evaluates ship's `exit_gates` (via `_forward_gate_blocks`/
`decide_transition`); if a reset bypasses gate evaluation, host the leaf on
`sdd-verify-and-review.yaml` (`qa → ship`) instead — the predicate is identical.
Then, in `sdd-deliver-and-ship.yaml`: append `- lessons_recorded:` to
`exit_gates.all_of`; extend the "Checkpoint first" paragraph and §3 "Record the
delivery" so `raw_prose` instructs writing `docs/solutions/<slug>.md` and
literally contains the `docs/solutions/` token (which `derive_invariants` now
requires — the prose and gate must move together); update `change_summary` to
include the override-migration note (a pre-existing profile override lacking the
token is dropped at runtime until re-added). Keep `prose_invariants`
(`agentalloy phase set intake`) intact.

## Test cases

- TC1 (AC 1): the composed ship gate blocks close-out without the lesson.
- TC3 (AC 3): loading the shipped skill yields no invariant-violation warning;
  `raw_prose` contains `docs/solutions/`.
- TC8 (AC 8): `change_summary` states the token + drop behavior.
