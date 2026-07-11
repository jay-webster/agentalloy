# mcp-tool-trust-guardrail — Test Plan

## Test Cases

### Task 1/2 — structure and inspection (no automated test suite for pack content; verified by tooling + inspection)

- **T1.1 (AC1).** Side-by-side field comparison against
  `incident-response.yaml`: all required top-level fields present, same
  shape.
- **T1.2 (AC1).** `raw_prose` content, when split by heading, matches the
  fragments' content and ordering exactly.
- **T1.3 (AC3).** `pack.yaml`'s new entry's `fragment_count` equals the
  actual number of `fragments` entries in the new skill file (manual
  count, cross-checked).

### Task 3 — validation

- **T3.1 (AC2).** `agentalloy validate-pack src/agentalloy/_packs/core`
  passes (or passes with `--allow-lint-warnings` if only non-blocking lint
  issues are flagged — real strict-mode errors must be fixed, not
  suppressed).

### Task 4 — scope and sourcing checks

- **T4.1 (AC4).** `change_summary` names the real message_id, the real
  disclosed attack classes, and correctly attributes the lethal-trifecta
  framing to "per the source article" rather than independent
  verification.
- **T4.2 (AC5).** The `example` fragment's description of
  `injection_guard.py`/`evaluate()`'s behavior is checked against the
  actual shipped code (already merged via PR #3) for accuracy.
- **T4.3 (AC6).** `git diff --stat` shows exactly two files touched.
- **T4.4 (AC7).** Confirm the session's own commands: `git push` to a
  named branch, no `gh pr create` call made.
