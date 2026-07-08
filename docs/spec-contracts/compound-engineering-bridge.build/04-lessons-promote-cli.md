---
phase: build
task_slug: 04-lessons-promote-cli
route: full
domain_tags:
  - cli-subcommand
scope:
  touches:
    - "src/agentalloy/install/subcommands/**"
    - "tests/**"
  avoids:
    - "src/agentalloy/code_index/**"
    - "src/agentalloy/api/**"
success_criteria: []
related_contracts: []
created_at: 2026-07-08T00:00:00Z
---

# 04-lessons-promote-cli

## Task

Add `src/agentalloy/install/subcommands/lessons.py` registering
`agentalloy lessons promote <slug>` (via `add_parser`, wired in the CLI
dispatcher). Flow: run the task-03 generator for `<slug>`; **pre-ingest dedup
probe** — embed the candidate fragments with the same embed provider the rail
uses and run `dedup_gate.classify_hit` against the corpus; on a hard hit
(≥ 0.92) refuse with a non-zero exit naming the near-duplicate skill, unless
`--allow-duplicates` downgrades it to a warning; on soft hit warn and proceed;
then install by calling the existing `install_local_pack` (strict). Prevention,
not cleanup — a hard duplicate must never reach the corpus (the rail does not
roll back on its own).

## Test cases

- TC5 (AC 5): near-identical lesson (≥ 0.92) → refused, non-zero, and no new
  skill row/vector afterward; `--allow-duplicates` proceeds with a warning.
- Edge: a unique lesson installs cleanly (exit 0) and the skill is present.
- Edge: unknown `<slug>` (no `docs/solutions/<slug>.md`) → clear usage error.
