# automation-risk-classifier — Test Plan

## Test Cases

### Task 1

- **T1.1 (AC1).** `classify(["src/agentalloy/_packs/core/x.yaml",
  "docs/y.md"])` → `"low"`.
- **T1.2 (AC2).** `classify(["src/agentalloy/_packs/core/x.yaml",
  "automation/store.py"])` → `"high"` (one disallowed path disqualifies
  the whole change).
- **T1.3 (AC3).** `classify(["src/agentalloy/retrieval/hybrid.py"])` →
  `"high"`.
- **T1.4 (AC4).** `classify([])` → `"high"`, explicitly asserted (not
  merely "whatever it happens to return").
- **T1.5.** `LOW_RISK_PATH_PREFIXES` contains exactly
  `"src/agentalloy/_packs/"` and `"docs/"` — asserted directly against the
  constant, not inferred from function behavior alone.

### Task 2 — live proof

- **T2.1 (AC6).** `classify(["src/agentalloy/_packs/core/mcp-tool-trust-guardrail.yaml",
  "src/agentalloy/_packs/core/pack.yaml"])` — the real changed-file list
  from tonight's dry-run branch — → `"low"`.
