---
phase: build
task_slug: 05-guards-and-docs
route: full
domain_tags:
  - testing
scope:
  touches:
    - "tests/**"
    - "README.md"
  avoids:
    - "src/agentalloy/code_index/**"
    - "src/agentalloy/retrieval/**"
    - "src/agentalloy/api/**"
success_criteria: []
related_contracts: []
created_at: 2026-07-08T00:00:00Z
---

# 05-guards-and-docs

## Task

Lock the feature's boundaries and document it. Add a guard test asserting the
feature diff touches no file under `src/agentalloy/code_index/`,
`src/agentalloy/retrieval/`, or `src/agentalloy/api/`, and that a repo containing
`docs/solutions/x.md` still returns that chunk from `agentalloy code search` with
no code change (AC 6). Add an opt-out test: under `lifecycle-mode off` the ship
gate/codify prompt never compose, and under `flow free` workflow steering is
paused (AC 7). Add a short README note framing codify-at-ship + lesson promotion
as the first concrete slice of the roadmapped **Knowledge** module.

## Test cases

- TC6 (AC 6): no diff under code_index/retrieval/api; `docs/solutions/*.md`
  retrievable via `code search`.
- TC7 (AC 7): gate + prompt inert under `off` and `flow free`.
- Doc: README references the Knowledge-module slice.
