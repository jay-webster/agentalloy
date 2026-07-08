---
phase: build
task_slug: 02-qa-ship-gate-and-codify-prose
route: full
domain_tags:
  - workflow-gates
scope:
  touches:
    - "src/agentalloy/_packs/sdd/sdd-verify-and-review.yaml"
    - "tests/**"
  avoids:
    - "src/agentalloy/_packs/sdd/sdd-deliver-and-ship.yaml"
    - "src/agentalloy/signals/**"
    - "src/agentalloy/api/**"
success_criteria: []
related_contracts: []
created_at: 2026-07-08T00:00:00Z
---

# 02-qa-ship-gate-and-codify-prose

## Task

Wire Piece 1 into the **qa** workflow skill (spike D2 established that ship's own
`exit_gates` are unenforceable — the `ship → intake` reset and all backward jumps
bypass gate evaluation; the real forward edge is `qa → ship`). In
`sdd-verify-and-review.yaml`: append `- lessons_recorded:` to `exit_gates.all_of`
(beside the existing `docs/qa/*.md` leaves); extend the qa prose so the agent
writes `docs/solutions/<slug>.md` as the final step before advancing, and so
`raw_prose` literally contains the `docs/solutions/` token; assert that token as
an invariant (an authored `prose_invariants` entry, or via the predicate's
advisory `path` arg) so prose and gate stay consistent; update `change_summary`
with the override-migration note (a pre-existing profile override lacking the
token is dropped at runtime until re-added). Keep the qa `prose_invariants`
(`agentalloy phase set ship`) intact.

## Test cases

- TC1 (AC 1): the composed `qa → ship` gate blocks `phase set ship` without the
  lesson; passes once written.
- TC3 (AC 3): loading the shipped qa skill yields no invariant-violation warning;
  `raw_prose` contains `docs/solutions/`.
- TC8 (AC 8): `change_summary` states the token + drop behavior.
