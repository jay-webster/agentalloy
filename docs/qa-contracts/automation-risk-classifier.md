# automation-risk-classifier — QA Report

## Checks

- **New tests**: 5 added (`test_risk_classifier.py`) — all-allowlisted →
  low, one disallowed path → high (even with everything else allowlisted),
  all-disallowed → high, empty input → high (explicit), constant contents
  asserted directly. All of slices 1-7's existing 54 tests still pass
  unmodified. **59 total in `tests/automation/`.**
- **Lint**: `uv run ruff check automation/ tests/automation/` — clean.
  `uv run ruff format --check` — clean.
- **Type checker**: `uv run pyright automation/` — **0 errors**, same 9
  pre-existing warnings as slice 6, no new ones (`risk_classifier.py` is
  fully typed — `list[str]` in, `Literal["low", "high"]` out, no untyped
  external data involved at all).
- **Scope check (AC5)**: `git status --short` shows only
  `automation/risk_classifier.py` and `tests/automation/test_risk_classifier.py`,
  both new. Zero paths under `src/agentalloy/`.
- **Determinism check (AC5)**: `grep -rn "lm_client\|embed"
  automation/risk_classifier.py` — zero hits. Pure path-string matching,
  no I/O, no subprocess, no new dependency.
- **Live proof (AC6)**: ran `classify()` against the real changed-file
  list from the `agentalloy-guardrail-mcp-injection` branch (8 files:
  6 `docs/...` contract files plus 2 `src/agentalloy/_packs/core/...`
  files — pulled via `git diff --name-only main
  origin/agentalloy-guardrail-mcp-injection`, not hand-picked) — returned
  `"low"`. This is real evidence against an already-shipped, already-QA'd
  diff from earlier tonight, not a synthetic fixture built to pass.

## Review

### Acceptance criteria (against `docs/spec-contracts/automation-risk-classifier.spec.md`)

1. **All-allowlisted → low — MET.** `test_all_allowlisted_paths_classify_low`.
2. **One disallowed path → high, disqualifies the whole change — MET.**
   `test_one_disallowed_path_makes_whole_change_high` (mixed allowlisted +
   disallowed, still `high` — confirms it's not a majority-vote or any-
   match logic).
3. **All-disallowed → high — MET.** `test_all_disallowed_paths_classify_high`.
4. **Empty input handled explicitly — MET.** `test_empty_input_classifies_high`,
   plus the design's explicit early-return (not relying on `all()`'s
   vacuous-truth default) confirmed by code inspection.
5. **No product code touched, no new dependency, no LLM call — MET.**
   Scope and determinism checks above.
6. **Live proof against a real diff — MET.** See Checks — the diff was
   pulled programmatically from the real branch, not constructed to match.

### Non-goals respected

Checked against the spec's Out of Scope: no merge/deploy wiring exists in
this slice — `classify()` returns a string, nothing calls `gh pr merge` or
anything else with it; the allowlist is exactly the two prefixes named in
the spec, not expanded; no SDD-execution generation attempted.

### Design conformance

Matches `approach.md` on every decision: `startswith()` prefix matching,
not glob (appropriately simple for two directory prefixes); empty input
fails closed to `high`, implemented as an explicit early return, verified
present in the actual code, not just tested behaviorally; the allowlist is
a named, top-level, directly-importable constant (confirmed —
`test_low_risk_path_prefixes_contents` imports and asserts it directly).

### Findings

- **Required**: none.
- **Critical**: none.
- **Nit**: none.
- **Dead code**: none.

## Verdict

Clean. All 6 acceptance criteria met, including a live proof against a
real, previously-shipped diff rather than a constructed fixture. This is
the first concrete piece toward Jay's stated auto-merge/auto-deploy goal —
deliberately just the classification logic, with the actual merge
mechanism still explicitly gated on GitHub Actions being confirmed live on
the fork. Ready to route to ship.
