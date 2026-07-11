# Automation Auto Merge Gate

> **Scope in a sentence.** Wire the already-built, already-tested risk
> classifier into GitHub's native auto-merge: a PR whose real diff
> classifies `low` gets auto-merge enabled automatically; a `high`
> classification changes nothing, leaving the PR exactly as manual-merge
> as it is today.

> **Location note.** At runtime the SDD spec phase writes the spec to
> `docs/spec/automation-auto-merge-gate.md`, git-ignored. This file is the
> committed, reviewable copy.

## Context

`automation/risk_classifier.py` (shipped in PR #8) already does the hard
part: `classify(changed_paths) -> "low"|"high"`, fails closed, unit
tested. It was deliberately left unwired — its own spec named the exact
blocker: "Auto-merge is meaningless without real, enforced CI checks
behind it," and at the time GitHub Actions had never run on this fork at
all.

That blocker is now cleared. PR #9 (`automation-gemini-review`) proved
Actions runs for real, through four rounds of live testing that fixed ten
genuine bugs (a false-positive-pass `pipefail` gap, two regressions, two
real transient-network failure modes correctly surfaced rather than
swallowed). PR #10 fixed the last piece of pre-existing debt blocking
`quality` from ever going green. As of now, every check on this repo
(`quality`, `review`, `container-tests`, `web-build`, `pipx-smoke`) has a
real, live-verified track record — the precondition this slice was
waiting on.

**Still true today, unchanged since PR #8 shipped:** `main` has no branch
protection, and the repo's `allow_auto_merge` setting is `false`. Turning
those on is a GitHub *settings* change, not a code change — this session's
standing rule is to ask before any hard-to-reverse or account-setting
action, and enabling branch protection / auto-merge on Jay's real fork
qualifies. This slice builds and ships the code (workflow + classifier
glue) in the normal way, then explicitly stops and asks before flipping
the two GitHub settings required to make it live, and again before the
live-proof step that opens a real PR to prove it end-to-end.

## Assumptions (correct these before design)

- **The classifier decides auto-merge *eligibility*, not the merge gate
  itself.** GitHub's own required-status-checks mechanism (once branch
  protection is configured) is what actually blocks a bad merge — for
  every PR, low-risk or high-risk alike. The risk classifier's only job is
  to decide whether to call `gh pr merge --auto`, i.e. whether a human
  needs to be in the loop at all. A `high` classification must never
  block Jay from manually merging something himself after review — it
  only means the automation won't do it for him.
- **`gh pr merge --auto --squash`** is the mechanism, matching this repo's
  existing squash-merge convention (every PR merged so far tonight was
  squash-merged). GitHub only actually performs the merge once all
  required status checks pass — enabling auto-merge on a PR that never
  goes green just leaves it pending, same as today.
- **This repo currently has exactly one real contributor** (Jay, plus this
  session's own automation-authored PRs). No fork-PR / untrusted-author
  hardening is in scope for this slice — noted as a real gap to revisit if
  that ever changes, not solved now.
- **The low-risk allowlist itself is untouched.** `src/agentalloy/_packs/`
  and `docs/` remain the only low-risk prefixes; expanding that list is a
  separate, deliberate future decision.

## What

**New CI glue script**, `automation/ci/auto_merge_gate.py`, following the
same deterministic/impure split as `gemini_review.py`: reads changed paths
(one per line) from stdin, calls the existing `risk_classifier.classify()`
unchanged, prints `low` or `high` to stdout. No new logic beyond this thin
wrapper — `classify()` itself is not touched or re-tested here (already
covered by its own slice's tests).

**New workflow**, `.github/workflows/auto-merge-gate.yml`, triggered on
`pull_request: [opened, synchronize, reopened]`: computes the real changed
paths via `git diff --name-only` against the PR base (passed through an
env var, not spliced into the shell string — the exact pattern fixed in
`gemini-review.yml` after a real finding), pipes them through the new
script, and calls `gh pr merge <PR> --auto --squash` only when the result
is `low`. A `high` result is a deliberate no-op — the PR is left exactly
as manual-merge as any PR is today.

**No change to `risk_classifier.py`, `gemini_review.py`, or any existing
workflow's required-check behavior.** This slice only adds new files and,
later — after explicit confirmation — GitHub-side settings.

## Acceptance Criteria

1. **`auto_merge_gate.py`'s stdin-to-classification path is correct and
   tested**, reusing `risk_classifier.classify()` unmodified. Verifiable
   by unit tests covering: all-low-risk paths → `low`; any high-risk path
   present → `high`; empty stdin → `high` (matches `classify([])`'s
   existing fail-closed behavior).
2. **The workflow enables native GitHub auto-merge exactly when the
   classification is `low`, and takes no merge action when it's `high`.**
   Verifiable by code review of the workflow's conditional plus live proof
   (AC5/AC6).
3. **No product code touched.** Zero diff under `src/agentalloy/`; zero
   diff to `automation/risk_classifier.py` itself; zero diff to any
   existing workflow file.
4. **GitHub settings changes (branch protection requiring the five
   existing checks; repo-level `allow_auto_merge: true`) are proposed and
   applied only after explicit, separate confirmation from Jay in chat** —
   not bundled into the build/ship steps as something the code or this
   session does unilaterally. Verifiable by this QA report explicitly
   naming when/whether that confirmation was obtained before any setting
   was changed.
5. **Live proof, low-risk path**: after the settings in AC4 are live, open
   a real PR touching only an allowlisted path (e.g. `docs/`) and confirm
   auto-merge is enabled on it by the new workflow, and that it actually
   merges on its own once required checks go green — no manual `gh pr
   merge` from Jay or from this session.
6. **Live proof, high-risk path**: confirm a PR touching a path outside
   the allowlist (e.g. anything under `automation/` or `src/agentalloy/`
   outside `_packs/`) does **not** get auto-merge enabled — it remains a
   normal PR requiring Jay's manual merge, unchanged from today's
   behavior.
7. **No new external credential.** `gh pr merge --auto` runs inside GitHub
   Actions using the workflow's own `GITHUB_TOKEN` — no new secret to
   provision.

## Out of Scope

- **Expanding the low-risk allowlist.** `risk_classifier.py`'s
  `LOW_RISK_PATH_PREFIXES` is unchanged by this slice.
- **Auto-deploy.** Already solved by the existing `release-cut.yml` —
  unrelated to this slice, which only concerns merging, not releasing.
- **Content-level safety beyond what already exists.** This is a
  path-based gate layered on top of the existing `quality`/`review`/test
  checks; it does not add new content inspection.
- **Fork-PR / untrusted-author hardening.** Noted as a real gap (see
  Assumptions) but not solved here — no fork contributors exist on this
  repo yet.
- **Requiring human PR review/approval as part of branch protection.**
  Deliberately not added — the entire point of this slice is that
  low-risk changes proceed *without* requiring a human reviewer.
- **Actually flipping the two GitHub settings, or opening the live-proof
  PRs, without a fresh, explicit go-ahead from Jay** — see AC4. Building
  and merging the code for this slice does not itself authorize the
  settings change.

## Design surface (hand-off to the design phase)

- **Should a `high` classification post a visible PR comment** ("high
  risk — human merge required") for parity with how every other check
  always leaves a visible trace, or stay silent since the PR's own
  unchanged (non-auto-merging) state already communicates that? Design
  decides; lean toward silence to avoid comment noise stacking on top of
  Gemini's own review comment, but this is a judgment call, not settled
  here.
- **Exact required-check list for branch protection**: all five existing
  checks (`quality`, `review`, `container-tests`, `web-build`,
  `pipx-smoke`), or a subset judged actually meaningful as a merge gate?
  Design confirms which.
- **Whether `include administrators` should be set on the branch
  protection rule** (i.e. does it apply to Jay's own manual merges too, or
  can he bypass it as repo owner). Given Jay merged PR #9 and #10 manually
  tonight without incident, leaning toward *not* restricting his own
  manual merges — but this is exactly the kind of GitHub-settings
  judgment call that should be surfaced explicitly, not assumed.
