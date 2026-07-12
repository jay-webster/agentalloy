# automation-auto-merge-gate — Lesson

## Problem

Wire the already-built, already-tested risk classifier into GitHub's
native auto-merge, so a low-risk PR merges itself once required checks
pass, without needing Jay to click merge.

## What didn't work / had to be corrected

**A real, live incident, not a hypothetical:** the original design assumed
`allow_auto_merge: false` at the repo level would make `gh pr merge --auto`
either error out or no-op harmlessly on a repo with no branch protection.
That assumption was wrong, and it caused a real, unintended production
merge.

What actually happened: once `auto-merge-gate.yml`'s `contents: write`
permission gap was fixed (a separate, real bug — see below), the very
next real low-risk PR to reach `gh pr merge --auto --squash` **merged
immediately**, for real, without ever going through the settings
checkpoint this slice's own spec had named as a hard requirement before
any live auto-merge behavior should occur.

**Root cause**: `gh pr merge --auto` only *defers* — waits for required
status checks, then merges later — when branch protection actually
defines required checks for that branch. With no branch protection at
all, there is nothing to wait for, so a PR that already looks mergeable
(all optional checks green, no protection blocking it) merges *right
now*, regardless of what `allow_auto_merge` is set to. `allow_auto_merge`
turns out to gate whether a *pending, deferred* auto-merge request can be
registered — it doesn't come into play at all when there's nothing to
defer to in the first place. Branch protection (required status checks)
is the thing that actually makes `--auto` behave as "wait, then merge"
instead of "merge now" — a repo-settings dependency the original design
missed entirely, having reasoned only about `allow_auto_merge` in
isolation.

**A second, unrelated real bug in the same incident**: `permissions:
pull-requests: write` alone was insufficient for `gh pr merge --auto` —
enabling or performing a merge is a content-changing GraphQL mutation and
needs `contents: write` too. This surfaced first (`GraphQL: Resource not
accessible by integration`), and fixing it is what then exposed the
branch-protection gap on the very next attempt — two independent bugs,
discovered back-to-back because the first one had been quietly masking
the second.

**Immediate response, in order**: disabled the `Auto Merge Gate` workflow
the moment the unintended merge was discovered (fully reversible,
one command, stops any further surprise merges instantly); reported the
incident to Jay transparently rather than downplaying a benign-content
outcome; only then set up branch protection — with Jay's fresh, explicit,
scoped confirmation for that specific setting, not bundled with the
adjacent `allow_auto_merge` change even though both are needed for the
feature to work end-to-end, because Jay's instruction named only branch
protection.

## Decisions worth keeping

- **Test settings changes against their actual documented interaction,
  not each one in isolation.** `allow_auto_merge` and branch protection
  are not independent switches — the auto-merge feature only exists in
  the space *between* them (protection defines what to wait for;
  `allow_auto_merge` permits the waiting). Reasoning about either one
  alone, as this slice's original spec did, misses the real behavior.
- **When an automated action produces an unintended real-world side
  effect, the first move is to stop the mechanism, not to explain it
  away.** Disabling the misbehaving workflow took one command and cost
  nothing; leaving it live "while explaining" would have left every
  subsequent low-risk PR exposed to the same surprise.
- **A permission-scope request should be read literally, not expanded to
  "what's obviously also needed."** Asked to set up branch protection,
  attempting to also flip `allow_auto_merge` in the same step — even with
  a clear, stated rationale — was correctly denied. The fix for wanting
  two things is asking for both, explicitly, not inferring consent for
  the second from the first.
