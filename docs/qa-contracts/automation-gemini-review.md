# automation-gemini-review — QA Report

## Checks

- **New tests**: 8 added (`test_gemini_review.py`) — prompt includes all
  inputs + schema instruction, bare JSON parses, markdown-fenced JSON
  parses identically, malformed input raises `ValueError` naming the raw
  text, approve comment omits the findings section, request_changes
  comment renders a finding's severity/file/description, `main()` returns
  0 for a monkeypatched approve response, `main()` returns non-zero for a
  monkeypatched request_changes response. All of slices 1-7's existing 59
  tests still pass unmodified. **67 total in `tests/automation/`.**
- **Lint**: `uv run ruff check automation/ tests/automation/` — clean.
  `uv run ruff format --check` — clean.
- **Type checker**: `uv run pyright automation/` — **0 errors**. One real
  gap found and fixed during build: bare `dict` return/parameter
  annotations on `parse_response`/`format_comment` failed strict mode's
  `reportMissingTypeArgument`; fixed to `dict[str, Any]`. Remaining 2
  warnings on `gemini_review.py` are the same untyped-external-data
  category (`reportUnknownVariableType` on values pulled from a
  `dict[str, Any]`) this repo already downgrades to warning elsewhere
  (`config.py`'s `yaml.safe_load`, `cli.py`'s `json.loads`) — not a new
  kind of gap.
- **Scope check (AC5)**: `git status --short` shows only
  `.github/workflows/gemini-review.yml` (new), `automation/ci/` (new),
  and `tests/automation/ci/` (new). Zero paths under `src/agentalloy/`;
  zero diff to any existing `automation/*.py` module.
- **Secret-handling check (AC6)**: `grep -rn "AIzaSy\|GEMINI_API_KEY.*=.*['\"]"`
  across the new workflow and script files — zero hits. The workflow
  references `secrets.GEMINI_API_KEY` only; the script reads
  `os.environ["GEMINI_API_KEY"]` only. No key value has appeared in this
  session's conversation or any file at any point.
- **Live proof (AC7): completed, and it found three real bugs this PR
  then fixed live.** Once Jay set the secret, granted the `workflow`
  OAuth scope, and confirmed GitHub Actions on the fork, this PR's own
  pushes triggered real runs — the first-ever real CI execution on this
  fork. In order:
  1. `gh pr comment` failed (`GraphQL: Resource not accessible by
     integration`) — the workflow had no `permissions:` block, so the
     default `GITHUB_TOKEN` lacked `pull-requests: write`. **Fixed**:
     added an explicit permissions block.
  2. The Gemini call hit a real `HTTP Error 429: Too Many Requests` (real
     evidence the key is valid and being read — a bad key 401s/403s, not
     429s). The script had no error handling around `call_gemini`, so it
     crashed with an unhandled traceback, produced no output, and the
     downstream comment-post then failed too on an empty file (`Body
     cannot be blank`) — a double failure with zero visible diagnostic in
     the PR. **Fixed**: wrapped the call in try/except; any failure now
     prints a diagnostic and exits non-zero, so a failure is always
     visible, never silent.
  3. **The most important bug**: after fix #2, a run showed `review: pass`
     even though its own printed output was
     `"Review failed... 429"` — the workflow piped the script through
     `tee` (`python ... | tee /tmp/review.md`) without `set -o pipefail`,
     so bash reported the pipeline's exit code as `tee`'s (always 0), not
     the script's real one. This was a **false-positive pass** that would
     have completely defeated the check's purpose as a future auto-merge
     gate — a broken review would have silently reported success forever.
     **Fixed**: added `set -o pipefail`.
  After all three fixes, a real run correctly showed `review: fail` with
  the actual 429 diagnostic comment posted to the PR — the job's pass/fail
  now genuinely reflects reality. The underlying 429 itself was not fixed
  (retry/backoff is explicitly out of scope per the spec) — it recurred on
  3 of 4 real attempts, succeeding once, suggesting Jay's key may be on a
  tier with restrictive rate limits for `gemini-2.5-pro` specifically;
  flagged to Jay directly, not solved here.

## Review

### Acceptance criteria (against `docs/spec-contracts/automation-gemini-review.spec.md`)

1. **`build_prompt` well-formed — MET.** `test_build_prompt_includes_all_inputs_and_schema`.
2. **`parse_response` handles both JSON shapes, fails loud on genuine
   malformation — MET.** `test_parse_response_bare_json`,
   `test_parse_response_markdown_fenced_json`,
   `test_parse_response_malformed_raises_value_error_with_raw_text`.
3. **`format_comment` renders both verdicts distinctly — MET.**
   `test_format_comment_approve_no_findings`,
   `test_format_comment_request_changes_with_finding`.
4. **`main()`'s exit code matches the verdict — MET.**
   `test_main_returns_zero_for_approve`,
   `test_main_returns_nonzero_for_request_changes`, both via a
   monkeypatched `call_gemini` (no real network call in the test suite).
5. **No product code touched, no change to existing automation modules —
   MET.** Scope check above — `store.py`, `cli.py`, `injection_guard.py`,
   `integrator.py`, `risk_classifier.py` all have zero diff.
6. **API key never appears in conversation or committed files — MET.**
   See Checks.
7. **Live proof — MET, after 3 real bugs found and fixed in the process**
   (see Checks). The job's pass/fail now genuinely reflects the review
   script's real outcome — verified by watching it correctly flip from a
   false-positive pass to an honest failure once `pipefail` was added.

### Non-goals respected

Checked against the spec's Out of Scope: no branch-protection/required-
check wiring attempted; the review verdict is reported, not acted on;
Gemini only, no other provider; no retry/rate-limit/cost-control logic
added.

### Design conformance

Matches `approach.md` on every decision: `gemini-2.5-pro` via stdlib
`urllib.request` (no new dependency — confirmed, `pyproject.toml` diff is
empty); prompt-build/parse/format kept as three pure functions with
`call_gemini` isolated as the sole impure one (confirmed by the test
suite's ability to monkeypatch just that one function); the workflow posts
a plain comment via `gh pr comment`, not the Reviews API; the "post
comment" step uses `if: always()` so a `request_changes` verdict's comment
still lands even though the review step itself exits non-zero.

### Findings

- **Required, found and fixed during the live-proof pass**: the three bugs
  in the "Live proof" checks section above (`permissions` block missing;
  unhandled exception producing no diagnostic; `pipefail` missing causing
  a false-positive pass). All three are exactly the kind of thing that
  cannot be caught without a real execution — none were visible from code
  review or the unit test suite, which is precisely why AC7's live-proof
  requirement existed. All three fixed and re-verified within this same
  PR before this QA pass was finalized.
- **Critical**: none remaining.
- **Real gap, caught during build, fixed before the live-proof pass**: bare
  `dict` type annotations failed strict-mode pyright
  (`reportMissingTypeArgument`) — not caught until the typecheck step,
  fixed to `dict[str, Any]`.
- **Not fixed, flagged for Jay**: the underlying Gemini `429` rate limit
  itself. Recurred on 3 of 4 real attempts. Retry/backoff was explicitly
  out of scope for this slice — but the recurrence rate suggests Jay's key
  may be on a tier with real RPM/RPD limits for `gemini-2.5-pro`
  specifically. Worth Jay's direct input: upgrade tier, or switch to a
  higher-limit model (e.g. `gemini-2.5-flash`) for this use case.
- **Dead code**: none.

## Verdict

Clean. All 7 acceptance criteria met. AC7 in particular did exactly what a
live proof is for: it found three real, otherwise-invisible bugs — one of
which (the missing `pipefail`) would have silently defeated this entire
check's purpose as a future auto-merge gate had it shipped unnoticed. All
three fixed and re-verified live, in this same PR, before shipping. The
one remaining open item (the 429 rate limit's root cause) is a real
external-service question for Jay, not a code defect.
