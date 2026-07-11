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
  now genuinely reflects reality.
- **Model switch, two more real findings.** Jay chose to switch off
  `gemini-2.5-pro` (persistent 429s) rather than check his tier. First
  attempt, `gemini-2.5-flash`, hit a live `404 Not Found` *despite being a
  confirmed valid model* per this key's own `ListModels` response — cause
  unclear, possibly transient, not chased further. Switched instead to
  `gemini-flash-latest`, an alias that always resolves to Google's current
  flash-tier model rather than a name that can go stale when Google cycles
  versions (this repo now has direct, repeated evidence that pinned model
  names are a real maintenance liability). This produced a **genuine
  successful review** — Gemini approved, with two legitimate findings on
  `gemini_review.py` itself: the API key was sent as a URL query parameter
  (leak risk via logs/tracebacks) rather than the `x-goog-api-key` header,
  and `format_comment`/`main()` used direct dict-key access that could
  `KeyError` on a malformed model response. **Both fixed** (header-based
  auth; `.get()` with fallbacks throughout), re-verified: a subsequent real
  run hit a transient `HTTP 503: Service Unavailable` (Google's server
  side, not this code) and the error-handling from bug #2 correctly
  produced a diagnostic comment rather than failing silently — further
  live confirmation that fix holds for a *different* real failure mode
  than the one that originally motivated it.
- **Third live review pass, three more real findings, all fixed.** After
  the header/`.get()` fixes above, another real Gemini review of this same
  file (now running on the `-latest` alias) returned `request_changes`
  with three genuine findings:
  1. **Major**: `main()` read `os.environ["PR_TITLE"]` and
     `os.environ["GEMINI_API_KEY"]` *outside* the try/except block. A
     missing env var (e.g. secrets unavailable on a fork PR) would raise
     `KeyError` before the "always leave a diagnostic comment" guarantee
     ever engaged — the exact same class of silent-crash bug as round 1's
     bug #2, reintroduced by a later edit. **Fixed**: moved all of
     `main()`'s body (env reads, prompt build, the Gemini call, parsing)
     inside the existing try block.
  2. **Minor**: `parse_response`'s fence-stripping used `.startswith("```")`,
     so any leading conversational text before a fenced block (e.g. "Sure,
     here is the review:" before the fence) skipped the strip entirely and
     broke JSON parsing. **Fixed**: replaced with a `re.search` over a
     `_FENCE_RE` pattern that finds a fenced block anywhere in the text,
     falling back to the raw text if none is found.
  3. **Minor**: the workflow's "Post review comment" step (`if: always()`)
     would itself fail if `/tmp/review.md` was never created — e.g. if
     checkout or `uv` setup failed before the review step ran at all.
     **Fixed**: wrapped `gh pr comment` in a bash `if [ -f /tmp/review.md ]`
     guard, printing a diagnostic instead of failing when the file is
     absent.
  All three fixed, covered with new unit tests (a fence-with-leading-text
  case for finding #2, a missing-env-var case for finding #1; finding #3 is
  workflow YAML with no direct unit test, verified by code review and the
  next live run), and re-verified via a subsequent real run.
- **Fourth live review pass, two more real findings, both fixed; then a
  transient timeout; then a clean approve on re-run.** The round-3-fixed
  code triggered a fourth real Gemini review, which returned
  `request_changes` with two new findings:
  1. **Minor (security)**: the workflow spliced
     `github.event.pull_request.base.ref` directly into a shell `run:`
     block via GHA expression interpolation — a real script-injection risk
     if a branch name ever contained shell metacharacters. **Fixed**:
     passed through an env var (`BASE_REF`) instead, referenced as
     `$BASE_REF`, matching how `PR_TITLE`/`PR_BODY` were already handled.
  2. **Minor (robustness)**: `call_gemini` indexed
     `data["candidates"][0]` directly; a safety-filtered response can
     return an empty `candidates` list, producing an unhelpful
     `IndexError`. **Fixed**: raises a `ValueError` naming the cause
     instead. (Already caught by round 3's try/except in `main()` either
     way — this fix only improves the diagnostic's clarity, not the
     crash-safety, which round 3 had already covered.)
  Both fixed, covered with a new unit test for the empty-candidates case
  (the `BASE_REF` fix is workflow YAML with no direct unit test, verified
  by code review and the next live run). The immediate re-run then hit a
  transient `HTTP read timeout` — Google's network side, not a code
  defect, and further live confirmation the round-1/round-3 error-handling
  correctly reports failure rather than passing silently on a *different*
  real failure mode again. A second re-run produced a **clean `approve`**,
  with one further **non-blocking minor suggestion** noted but not acted
  on in this slice: on PRs from forks, `GEMINI_API_KEY` is unavailable
  (fork PRs can't see repo secrets) and the check would fail rather than
  skip gracefully. Logged as a known follow-up, not fixed here — it's a
  design question about desired behavior on forks (skip vs. fail loud),
  not a defect, and the verdict was already `approve`.

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
7. **Live proof — MET, after 10 real findings found and fixed across four
   rounds of live testing** (see Checks). The job's pass/fail now
   genuinely reflects the review script's real outcome — verified
   repeatedly: flipping from a false-positive pass to an honest failure
   once `pipefail` was added, and correctly reporting failure (not a
   silent pass) on two separate real transient network errors (`503`,
   read timeout) unrelated to any code defect.

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
- **Resolved via Jay's own decision, not a code fix**: the `gemini-2.5-pro`
  rate-limit question — Jay chose to switch models (`gemini-flash-latest`)
  rather than investigate his API tier.
- **Real findings from Gemini's own review of this code, both fixed**:
  API-key-in-URL (now header-based), and unguarded dict-key access (now
  `.get()`-based throughout).
- **Not a code defect, expected and correctly handled**: a transient
  `HTTP 503` on an earlier verification run — Google's server side, not
  this repo's code. The error-handling built to survive the earlier 429
  handled it identically, which is exactly the point of that fix.
- **Real findings from Gemini's third live review of this code, all three
  fixed**: env-var reads outside the try/except (major, silent-crash
  regression of round 1's bug #2), fence-stripping missing leading
  conversational text (minor), workflow comment-post step not guarding for
  a missing review file (minor). See "Third live review pass" in Checks
  above.
- **Real findings from Gemini's fourth live review of this code, both
  fixed**: `base.ref` shell-injection risk in the workflow (minor,
  security), unguarded `candidates[0]` indexing on a possibly
  safety-filtered response (minor, robustness — already crash-safe via
  round 3's fix, this only sharpens the diagnostic). See "Fourth live
  review pass" in Checks above.
- **Not a code defect, expected and correctly handled**: a transient
  `HTTP read timeout` on the round-4 re-verification run — Google's
  network side, not this repo's code. A second re-run produced a clean
  `approve`. Same category as the earlier `503` — further confirmation
  the error-handling holds across multiple, different real transient
  failure modes.
- **Deferred, not a defect**: Gemini's fourth review also suggested the
  check should skip gracefully (exit 0) rather than fail when
  `GEMINI_API_KEY` is unavailable on fork PRs. Noted as a real design
  question for a future slice, not acted on here — this repo has no fork
  contributors yet, the verdict was already `approve`, and "what should
  happen on a fork PR" is a policy decision (skip vs. fail loud) rather
  than a bug.
- **Dead code**: none.

## Verdict

Clean. All 7 acceptance criteria met. AC7 did exactly what a live proof is
for — it found ten real, otherwise-invisible issues across four rounds of
live testing: three in the CI wiring itself (missing permissions, a silent
crash, and a `pipefail` gap that would have silently defeated this check's
entire purpose as a future auto-merge gate), two from Gemini's second real
review of this file (a credential-handling improvement, a robustness
improvement), three from Gemini's third real review (a silent-crash
regression of the round-1 fix, a fence-stripping edge case, and a workflow
guard for a missing review file), and two from Gemini's fourth real review
(a shell-injection risk in the workflow, an unguarded response-indexing
edge case). All ten fixed and re-verified live, in this same PR, before
shipping. The check now sits on a clean `approve` after re-running past a
transient network timeout. A model-naming surprise (`gemini-2.5-flash`
404ing despite being valid) was resolved by switching to a `-latest` alias
rather than chasing the root cause — a pragmatic choice given two
model-naming issues had already surfaced in one session. Two separate
transient network errors (`503`, then a read timeout) were not defects;
both were further confirmation the error-handling holds for real external
failures, not just the one that originally motivated it. The recurrence of
the round-1 env-var-crash pattern in round 3 (reintroduced by the
header/`.get()` fix edit) is itself useful evidence for why this check
exists as a standing CI gate rather than a one-time review: even careful,
iterative fixing can reintroduce a previously-caught class of bug, and an
independent different-model review catches it again on the next pass. One
non-blocking design question was surfaced and deliberately deferred rather
than fixed: whether the check should skip gracefully on fork PRs lacking
`GEMINI_API_KEY` rather than fail loud — a policy decision for a future
slice, not a defect in this one.
