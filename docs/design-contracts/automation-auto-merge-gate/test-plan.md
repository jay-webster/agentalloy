# automation-auto-merge-gate — Test Plan

## Test Cases

### Task 1 — `auto_merge_gate.py`

- **T1.1 (AC1).** stdin of all-allowlisted paths (e.g.
  `src/agentalloy/_packs/core/x.yaml\ndocs/y.md\n`) → prints `low`.
- **T1.2 (AC1).** stdin containing one non-allowlisted path alongside
  allowlisted ones → prints `high`.
- **T1.3 (AC1).** stdin of only non-allowlisted paths → prints `high`.
- **T1.4 (AC1).** empty stdin → prints `high` (matches `classify([])`'s
  existing fail-closed behavior).
- **T1.5 (AC1).** stdin with a trailing blank line (as real `git diff
  --name-only` output produces) does not corrupt the classification —
  same result as the equivalent input without the trailing blank line.

### Task 2 — workflow inspection

- **T2.1 (AC2).** Code review: the workflow's `if [ "$risk" = "low" ]`
  branch is the only path that calls `gh pr merge`; the `high` branch has
  no merge or comment action (approach.md §3).
- **T2.2 (AC2).** Code review: `BASE_REF` is read via `env:`, never
  spliced directly into the `run:` shell string (approach.md §2).
- **T2.3 (AC2).** Code review: `set -o pipefail` is the first line of the
  `run:` block.

### Task 3 — scope check

- **T3.1 (AC3).** `git diff --stat` against `main` shows only
  `automation/ci/auto_merge_gate.py`,
  `.github/workflows/auto-merge-gate.yml`, and this slice's test/contract
  files. Zero diff to `src/agentalloy/`, zero diff to
  `automation/risk_classifier.py`, zero diff to any existing workflow
  file.

### Task 4 — settings checkpoint

- **T4.1 (AC4).** This QA report explicitly states whether Jay was asked
  and what he said, before any branch-protection or `allow_auto_merge`
  setting was changed. No code test possible for a human confirmation
  step — verified by the QA report's own record.

### Task 5 — live proof, low-risk

- **T5.1 (AC5).** A real PR touching only `docs/` gets `gh pr view
  --json autoMergeRequest` showing auto-merge enabled, and later shows
  `state: MERGED` without a manual `gh pr merge` call from this session or
  Jay.

### Task 6 — live proof, high-risk

- **T6.1 (AC6).** A real PR touching `automation/` shows `gh pr view
  --json autoMergeRequest` as `null` (never enabled), and the PR remains
  open/mergeable-by-hand exactly as today.
