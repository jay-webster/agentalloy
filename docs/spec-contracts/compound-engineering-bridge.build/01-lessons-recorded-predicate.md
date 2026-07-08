---
phase: build
task_slug: 01-lessons-recorded-predicate
route: full
domain_tags:
  - deterministic-predicates
scope:
  touches:
    - "src/agentalloy/signals/predicates.py"
    - "tests/**"
  avoids:
    - "src/agentalloy/_packs/**"
    - "src/agentalloy/code_index/**"
success_criteria: []
related_contracts: []
created_at: 2026-07-08T00:00:00Z
---

# 01-lessons-recorded-predicate

## Task

Add a deterministic, DB-free predicate `lessons_recorded` to
`signals/predicates.py` and register it in the `PREDICATES` dict. It resolves the
**active task slug** from the ship work-item contract (do the D1 spike first:
confirm the canonical resolution — reuse `contracts.latest_contract`/the phase
cursor rule, not a raw newest-mtime guess), then returns `MET` iff
`docs/solutions/<slug>.md` exists, `NOT_MET` if it does not, and `UNKNOWN` if the
ship contract is missing/unreadable. Model it on `eval_approval_recorded` and
reuse `_glob_files`; keep it side-effect-free and independent of write order.

## Test cases

- TC1 (AC 1): `NOT_MET` with no `docs/solutions/<slug>.md`, `MET` once present.
- TC2 (AC 2): only `docs/solutions/<other>.md` present → `NOT_MET` for `<slug>`.
- Edge: missing/unreadable ship contract → `UNKNOWN` (never raises).
