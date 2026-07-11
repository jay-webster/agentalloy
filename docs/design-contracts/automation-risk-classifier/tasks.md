# automation-risk-classifier — Tasks

## Tasks

1. **`automation/risk_classifier.py` — `classify()` + `LOW_RISK_PATH_PREFIXES`.**
   Per approach.md §1-3. Pure function, no I/O, no dependency on
   `automation/store.py` or any other module. No dependency on other
   tasks. Satisfies AC1, AC2, AC3, AC4, AC5.

2. **Live proof against a real diff.** Run `classify()` against the real
   changed-file list from the `agentalloy-guardrail-mcp-injection` branch
   (already pushed, already QA'd tonight). Depends on Task 1. Satisfies
   AC6.
