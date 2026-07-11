# automation-auto-merge-gate — QA Report

## Checks

- **New tests**: 5 added (`test_auto_merge_gate.py`) — all-allowlisted
  paths print `low`; one disallowed path among allowlisted ones prints
  `high`; all-disallowed prints `high`; empty stdin prints `high`; a
  trailing blank line (matching real `git diff --name-only` output) does
  not corrupt the classification. **79 total in `tests/automation/`**
  (74 pre-existing + 5 new), all pass unmodified.
- **Lint**: `uv run ruff check .` — clean, whole repo. `uv run ruff format
  --check .` — clean, whole repo.
- **Type checker**: `uv run pyright automation/ci/` — **0 errors**. The
  10 warnings present are the same pre-existing untyped-external-data
  category on `gemini_review.py` already accepted in that slice's own QA
  report — nothing new from this slice's files.
- **Scope check (AC3)**: `git status --short` on this branch shows exactly
  three new files: `automation/ci/auto_merge_gate.py`,
  `tests/automation/ci/test_auto_merge_gate.py`,
  `.github/workflows/auto-merge-gate.yml`. Zero diff to `src/agentalloy/`,
  zero diff to `automation/risk_classifier.py` (imported unmodified), zero
  diff to any pre-existing workflow file.
- **Workflow inspection (AC2)**: confirmed by direct reading of
  `auto-merge-gate.yml` — `gh pr merge --auto --squash` is called only
  inside the `if [ "$risk" = "low" ]` branch; the `high` path has no
  merge call and no comment step (approach.md §3, deliberately silent to
  avoid stacking a second bot comment on every high-risk PR next to
  Gemini's own). `BASE_REF` is read via `env:` and referenced as
  `$BASE_REF`, never spliced into the `run:` string — the exact pattern
  fixed in `gemini-review.yml` after its own round-4 shell-injection
  finding, applied here from the start rather than discovered live.
  `set -o pipefail` is the first line of the `run:` block — the exact
  false-positive-pass lesson from `gemini-review.yml`'s round-1 bug,
  likewise applied preemptively.
- **Live proof of the workflow itself (real, found and fixed): the very
  first real CI run of this PR's own `gate` job failed with
  `ModuleNotFoundError: No module named 'automation'`.** Root cause:
  `uv run python automation/ci/auto_merge_gate.py` (invocation by file
  path) sets `sys.path[0]` to the script's own containing directory
  (`automation/ci/`), not the repo root — so `from automation.risk_classifier
  import classify` couldn't resolve. This was invisible to every prior
  test: `pytest`'s own config (`pyproject.toml`'s `pythonpath = ["src",
  "."]`) adds the repo root to `sys.path` for test runs, which is a
  different resolution mechanism than a real shell invocation gets. This
  is also the first script in `automation/ci/` to import from elsewhere in
  the `automation` package — `gemini_review.py` never hit this because it
  has zero cross-package imports, not because its invocation style was
  actually safe. **Fixed**: changed the workflow to invoke
  `uv run python -m automation.ci.auto_merge_gate` (module invocation,
  which puts the current working directory — the repo root, since `uv
  run` executes from there — on `sys.path`), matching the convention
  every other real invocation in this repo already uses (`automation/routines/*.md`
  all call `python -m automation.cli ...`, never by file path). Verified
  both locally (`echo path | uv run python -m automation.ci.auto_merge_gate`
  for both a `low` and a `high` case) and via a second live CI run.
  **Noted, not fixed here (out of scope for this PR):** `gemini-review.yml`
  still invokes its script by file path — currently harmless since that
  script has no cross-package import, but the same latent gap exists
  there and would resurface the moment that script ever needs to import
  a shared `automation.*` helper. Worth a follow-up if that file is
  touched again.
- **Settings checkpoint (AC4)**: **not yet reached.** Per approach.md §6
  and build task 45, this is an explicit checkpoint after this PR merges,
  not part of build/ship. No branch-protection or `allow_auto_merge`
  setting has been changed as part of this slice. To be recorded here
  (updated) once Jay is actually asked and answers.
- **Live proof (AC5, AC6)**: **not yet reached**, blocked on AC4 per the
  design's explicit sequencing (approach.md §6). Will be recorded here
  once performed.

## Review

### Acceptance criteria (against `docs/spec-contracts/automation-auto-merge-gate.spec.md`)

1. **`auto_merge_gate.py`'s stdin-to-classification path is correct and
   tested — MET.** `test_all_allowlisted_paths_prints_low`,
   `test_one_disallowed_path_prints_high`,
   `test_all_disallowed_paths_prints_high`, `test_empty_stdin_prints_high`,
   `test_trailing_blank_line_does_not_corrupt_classification`.
   `risk_classifier.classify()` is imported and used unmodified — zero new
   classification logic.
2. **Workflow enables auto-merge exactly on `low`, no-ops on `high` —
   MET.** See Checks, workflow inspection.
3. **No product code touched — MET.** See Checks, scope check.
4. **GitHub settings changes only after explicit confirmation — NOT YET
   REACHED.** Deliberately sequenced after this PR merges (see Checks).
   This QA report will be updated with what Jay was asked and what he
   answered once that conversation happens, before either setting is
   touched.
5. **Live proof, low-risk path — NOT YET REACHED.** Blocked on AC4.
6. **Live proof, high-risk path — NOT YET REACHED.** Blocked on AC4.
7. **No new external credential — MET.** The workflow uses only
   `github.token` (the built-in `GITHUB_TOKEN`), already used the same way
   in `gemini-review.yml`. No new secret provisioned or referenced.

### Non-goals respected

Checked against the spec's Out of Scope: `risk_classifier.py`'s
`LOW_RISK_PATH_PREFIXES` allowlist is untouched; no auto-deploy logic
added (already solved by `release-cut.yml`, untouched here); no new
content-level inspection; no fork-PR/untrusted-author hardening added
(explicitly named as a real, unaddressed gap, not hidden); branch
protection design does not require human review/approval (the whole point
of this slice is proceeding without one for low-risk changes).

### Design conformance

Matches `approach.md` on every decision: thin CLI wrapper reusing
`classify()` unmodified (§1); `BASE_REF`-via-env-var and
`set -o pipefail` reused from `gemini-review.yml`'s own hardening (§2);
silent no-op on `high` (§3); all five existing checks named as the
intended required-check list for the (not-yet-applied) branch protection
rule (§4); "include administrators" intentionally not set, so Jay's own
manual merges stay unaffected (§5); settings changes and live-proof PRs
explicitly deferred to a post-merge checkpoint rather than folded into
build/ship (§6).

### Findings

- **Critical**: none.
- **Dead code**: none.
- **Deliberately incomplete, not a defect**: AC4, AC5, AC6 are explicitly
  out of this PR's reach by design — this slice's own spec and design
  both name the GitHub-settings change and the live-proof PRs as a
  separate, later checkpoint requiring Jay's fresh go-ahead (see Context
  in the spec: this session's standing rule to ask before any
  hard-to-reverse account-setting change). Shipping the code now, with
  the checkpoint clearly marked, is the intended sequencing — not a gap
  in this QA pass.

## Verdict

**Partial — clean for what's in scope of this PR.** ACs 1, 2, 3, 7 are
fully met with real test coverage and direct inspection. ACs 4, 5, 6 are
deliberately deferred to a post-merge checkpoint (build task 45) that
requires Jay's explicit, fresh confirmation before any GitHub setting is
touched — consistent with this slice's own spec, which named that
sequencing as a requirement, not an oversight. This PR is safe to merge
on its own: it adds a new workflow that will run on every future PR
starting now, but its only live-behavior action is calling `gh pr merge
--auto` on a `low`-classified PR — expected to no-op or fail harmlessly
given `allow_auto_merge` is currently `false` at the repo level (GitHub's
documented behavior is to reject enabling auto-merge on a repo where the
setting is off), not yet verified live since AC4/AC5/AC6 haven't run.
Worth confirming as part of the settings checkpoint (task 45) rather than
assuming. No merge behavior actually changes until that checkpoint is
separately actioned and confirmed.
