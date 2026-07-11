# automation-gemini-review — Test Plan

## Test Cases

### Task 1 — pure functions

- **T1.1 (AC1).** `build_prompt("t", "d", "diff text")` includes the
  title, description, and diff text verbatim, plus the JSON-schema
  instruction substring.
- **T1.2 (AC2).** `parse_response('{"verdict": "approve", "summary": "ok",
  "findings": []}')` → parsed dict with those exact fields.
- **T1.3 (AC2).** `parse_response('```json\n{"verdict": "approve", ...}\n```')`
  → same successful parse (fence-stripping).
- **T1.4 (AC2).** `parse_response("not json at all")` → raises `ValueError`
  mentioning the raw text, not a bare `JSONDecodeError` traceback.
- **T1.5 (AC3).** `format_comment({"verdict": "approve", "summary": "looks
  good", "findings": []})` → includes "Approved", the summary, and no
  "Findings" section.
- **T1.6 (AC3).** `format_comment({"verdict": "request_changes", "summary":
  "issue found", "findings": [{"severity": "critical", "file": "x.py",
  "description": "bug"}]})` → includes "Changes requested", the finding's
  file/description/severity.

### Task 2 — `main()`

- **T2.1 (AC4).** With `call_gemini` monkeypatched to return a fixture
  `approve` response, `main()` returns `0`.
- **T2.2 (AC4).** With `call_gemini` monkeypatched to return a fixture
  `request_changes` response, `main()` returns non-zero.

### Task 3 — workflow inspection

- **T3.1 (AC5, AC6).** `git diff --stat` shows only
  `automation/ci/gemini_review.py`,
  `.github/workflows/gemini-review.yml`, and this slice's test/contract
  files. No literal API key value anywhere in the diff — inspected
  directly.

### Task 4 — live proof

- **T4.1 (AC7).** Once the secret is confirmed set: real PR triggers the
  real workflow; `gh run view` shows a completed run with a real
  conclusion (success or failure, both are valid proof it executed for
  real) — not "no runs found."
