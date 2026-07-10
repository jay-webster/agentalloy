# automation-drive-sync — Lesson

## Problem

Checking whether the pipeline could run unattended surfaced two gaps in
sequence: Gmail isn't an available connector for scheduled cloud routines,
and even if it were, a routine's fresh-git-clone-every-run environment has
no way to remember what it already processed. Both had to be closed before
"schedule the pipeline" was actually achievable.

## What worked

**Checking the actual claim before building around it.** "Can a scheduled
routine reach Gmail" was answerable in minutes by reading the `/schedule`
skill's own connector list, rather than assumed from "well Gmail worked in
this session." The gap (Drive/Calendar available, Gmail not) was
non-obvious and would have wasted real build time if discovered only after
committing to a design that assumed Gmail access.

**Realizing the state-persistence problem was a second, independent gap —
not solved by fixing the first one.** Finding a Gmail workaround (Drive
bridge) didn't automatically solve "does the routine remember anything
between runs." Naming that as its own question, rather than assuming the
Drive bridge would incidentally cover it, is what surfaced the actual
design needed here (download/upload the sqlite file itself around Drive).

**Reusing `add()`'s existing injection-guard screen for a brand new
ingestion path, by construction rather than by extra code.** Because the
screen lives inside `CandidateStore.add()` (a slice 3 decision), any new
path that calls `add()` — including one that didn't exist when slice 3 was
built — inherits the guard automatically. `test_import_jsonl_inherits_injection_guard`
exists specifically to prove this, not just assert it. This is the kind of
payoff that validates putting a guarantee at the lowest shared layer rather
than at each entry point.

**Being explicit about the one genuinely unverifiable piece instead of
stretching to claim more than was true.** The Apps Script half cannot be
run, tested, or deployed from this session — it requires Jay's own Google
account and OAuth consent. Rather than skip QA rigor for that half or
pretend a code-review pass was equivalent to a live run, the QA report
names the gap plainly and explains why no tool here can close it, matching
(not lowering) the honesty bar set by every prior slice's QA report.

## What didn't work / had to be corrected

**Branched off a stale local `main`.** `git fetch` updates the remote-
tracking ref, not the local branch — creating the feature branch from
local `main` right after a `fetch` (without a `pull`/`merge --ff-only`)
silently based it on a commit three PRs behind `origin/main`. Caught
immediately when the file being edited didn't contain code from the
just-merged prior slice. Fixed with a clean rebase (the only commit so far
was doc-only, so no conflicts). Going forward: after `git fetch`, actually
fast-forward local `main` before branching from it — don't trust that
`fetch` alone means `main` is current.

## Decisions worth keeping

- Verify a load-bearing assumption ("the routine can reach X") before
  designing around it, the same instinct as checking Gmail's OAuth
  status before building slice 1 — cheap to check, expensive to discover
  wrong after building.
- When two systems can't share a config file (this repo's Python package
  vs. a Google Apps Script running in a different account entirely), a
  literal, hardcoded, matching convention in both places (fixed filenames,
  fixed field names) is more reliable than trying to synchronize config
  across an unbridgeable boundary.
- `git fetch` is not `git pull` — always confirm local `main` is actually
  fast-forwarded before branching from it, not just fetched.
