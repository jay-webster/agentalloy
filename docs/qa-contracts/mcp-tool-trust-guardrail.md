# mcp-tool-trust-guardrail — QA Report

## Checks

- **Structural validation**: `uv run python -m agentalloy.install
  validate-pack src/agentalloy/_packs/core` — the new skill
  `mcp-tool-trust-guardrail` **PASSED**. All 4 failures in the run are
  pre-existing skills this change never touched
  (`test-driven-development`, `code-review-practices`,
  `planning-and-task-breakdown`, `incremental-implementation`) — confirmed
  by stashing this change and re-running against unmodified `main`: same 4
  failures, same messages, `8 passed / 4 failed / 12 total` (vs. this
  branch's `9 passed / 4 failed / 13 total` — exactly one more pass, zero
  new failures).
- **`raw_prose`/fragment consistency**: verified directly by the
  `validate-pack` pass above (this is exactly what that check enforces —
  "fragment content is not a contiguous slice of raw_prose" is the failure
  mode it would have reported). A typo (`sufond` → `sufficient`) was found
  and fixed in `raw_prose` during authoring, before the final validation
  run — caught by manual proofreading, not tooling, since the typo existed
  identically in both copies before the fix (so `validate-pack`'s
  consistency check alone wouldn't have caught it).
- **Manifest consistency**: `pack.yaml`'s new entry — `fragment_count: 7`
  — matches the actual 7 `fragments` entries in
  `mcp-tool-trust-guardrail.yaml`, counted directly.
- **Sourcing accuracy**: `change_summary` and the `rationale`/`guardrail`
  fragments were checked against this session's own retained knowledge of
  the source article (read in full earlier this session) — the two
  disclosed attack names (AutoJack, Agentjacking), the 85% figure, the
  100+ organizations figure, the 86%/29% adoption-readiness figures, and
  the "per the source article" (not independently verified) framing for
  the lethal-trifecta attribution are all accurate to what was actually
  read, not embellished or invented.
- **Example fragment accuracy**: the `example` fragment's description of
  `automation/injection_guard.py` and `CandidateStore.evaluate()` was
  checked against the actual shipped code (merged via PR #3,
  `automation-injection-guard`) — the described behavior (pattern screen
  at ingestion, structural refusal of `accept` on a flagged row before any
  write, `reject`/`needs_review` unaffected) matches the real
  implementation exactly.
- **Scope check**: `git status --short` / `git diff --stat` show exactly
  two files — `src/agentalloy/_packs/core/mcp-tool-trust-guardrail.yaml`
  (new) and `src/agentalloy/_packs/core/pack.yaml` (one version bump, one
  new list entry, no other line changed).

## Review

### Acceptance criteria (against `docs/spec-contracts/mcp-tool-trust-guardrail.spec.md`)

1. **Well-formed, matches pack convention — MET.** Field-by-field shape
   matches `incident-response.yaml`.
2. **Strict-mode fragment taxonomy — MET.** `validate-pack` pass confirms
   `raw_prose`/fragment consistency; the fragment list includes
   `execution` (x3), `verification`, `rationale` (strict mode's stated
   minimum), plus `guardrail` and `example`.
3. **`pack.yaml` consistent — MET.** New entry correct, version bumped
   `2.0.6` → `2.0.7`, no existing entry modified (confirmed by diff — only
   an addition, no other line touched).
4. **Sourcing real, not fabricated — MET.** See Checks — every cited
   figure and both attack-class names verified against this session's
   actual reading of the source.
5. **Example cites real, accurate mitigation — MET.** See Checks —
   checked against the actual shipped `injection_guard.py`/`evaluate()`
   code, not a paraphrase that drifts from it.
6. **No product code touched beyond the pack YAML and manifest — MET.**
   `git diff --stat` confirms exactly two files.
7. **Pushed to a branch, no PR, no merge — pending**, completed as the
   final action of this dry run (see below).

### Non-goals respected

No PR opened, no merge to `main` (see Delivery below). The
integrator-intake draft's thin "Original content" gap (found while
starting this dry run) was not fixed here — recorded as a finding for a
future slice, per the spec's Out of Scope. No other corpus or pack changed.

### Findings

- **Required**: none.
- **Critical**: none.
- **Real finding, not a code defect**: the integrator-intake draft's
  "Original content" section (`automation/intake-drafts/one-fake-sentry-...
  -19ef0107.md`) only carried the store's thin `snippet` field, not the
  actual article content that justified the `accept` verdict — that
  content was fetched live during evaluation and never persisted anywhere.
  This session's own retained knowledge of the source (from reading it
  during evaluation) substituted for what the draft should have provided.
  A future automated run of this same workflow — without a human's
  retained memory of the original content to fall back on — would have
  had only the thin snippet to work from. Worth a follow-up slice: should
  `evaluate()` optionally persist more of what was fetched during
  full-body evaluation, for exactly this hand-off case? Not fixed here —
  named for the next scoping conversation.
- **Nit**: one typo (`sufond`/`sufficient`) caught and fixed during
  authoring, before this QA pass — noted for completeness, not a
  remaining issue.
- **Dead code**: none.

## Verdict

Clean. All 7 acceptance criteria met (7 upon completing the push below).
This dry run proves the workflow: an `accept`-verdict candidate → a draft
intake artifact → a real SDD cycle (spec, design, build, validated
content) → a pushed branch, stopping deliberately short of a PR or merge.
That stopping point is the actual finding this exercise was designed to
test, not an incomplete step. Ready to push.
