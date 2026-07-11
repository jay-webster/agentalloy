# automation-risk-classifier — Lesson

## Problem

Jay's stated goal shifted tonight to full autonomy: auto-merge and
auto-deploy. Before building toward that, two real unknowns needed
resolving: what "deploy" actually means for this repo, and what replaces
human review as the safety net once it's removed.

## What worked

**Investigating existing infrastructure before designing anything.**
"Deploy" turned out to already be fully solved — `release-cut.yml`
auto-cuts a GitHub release whenever a version bump lands in a merged PR on
`main` with green CI. Reading `RELEASE.md` and the actual workflow file
before assuming anything needed to be built here avoided reinventing a
mechanism that already existed and was well-documented.

**Checking the real state of GitHub-side enforcement, not trusting the
repo's own documentation about itself.** `RELEASE.md` describes branch
protection, required checks, and `gh pr merge --auto` as the intended
workflow — but that document describes the *upstream* repo's conventions.
Checking the actual API state of Jay's fork (`branches/main/protection`,
`allow_auto_merge`, and — the real finding — zero workflow runs ever,
despite workflows showing "active") caught a gap that would have made any
auto-merge automation dangerously meaningless: arming auto-merge without
real CI behind it just merges instantly with no verification at all.

**Building the piece that doesn't depend on the blocked piece.** Rather
than stalling on Jay enabling GitHub Actions, the risk classifier — pure
logic, no GitHub dependency — was buildable and provable immediately. Same
pattern as every external-dependency wait tonight (Gmail reconnect, Apps
Script deployment): make progress on what's actually unblocked while the
blocking action happens in parallel.

**Fail-closed as the explicit, stated default for a safety gate.** Empty
input classifying `high` rather than `low` is the kind of decision that's
easy to get backwards accidentally (Python's `all()` on an empty iterable
is `True`, which would have silently produced `low` if the code had been
written slightly differently) — making the choice explicit, tested, and
justified in the design doc rather than an accident of language semantics
matters more for a function whose whole job is gating autonomous action.

## What didn't work / had to be corrected

Nothing required correction — clean first pass, same as most of tonight's
later slices.

## Decisions worth keeping

- Before building automation around an existing repo's CI/CD conventions,
  verify the actual current state (API calls, real run history) rather
  than trusting what the repo's own documentation says should be true —
  forks don't inherit branch protection or Actions enablement, and that
  gap is invisible until checked directly.
- When a user's goal shifts to something with materially higher risk (full
  autonomy vs. supervised slices), don't silently start building at the
  new risk level — name the shift explicitly, propose concrete safety
  mechanisms proportionate to the new stakes, and get confirmation on the
  approach before writing code.
- A classification/gating function that exists to authorize a risky action
  should fail closed on ambiguous input as a deliberate, tested choice —
  not an incidental consequence of whatever the underlying language
  primitives default to.
