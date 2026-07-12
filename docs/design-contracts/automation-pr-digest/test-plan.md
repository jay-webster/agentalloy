# automation-pr-digest — Test Plan

## Test Cases

### Task 1 — pure functions

- **T1.1 (AC1).** A PR with `createdAt >= since` appears in the "Opened"
  bucket with its title and link.
- **T1.2 (AC1).** A PR with `mergedAt >= since` appears in the "Merged"
  bucket.
- **T1.3 (AC1).** A currently-`OPEN` PR appears in "Still open" regardless
  of when it was created (not window-filtered).
- **T1.4 (AC1).** A merged PR with `mergedBy.is_bot: true` is labeled
  "auto-merged"; `is_bot: false` is labeled "manually merged"; missing/null
  `mergedBy` degrades to the label-free "merged".
- **T1.5 (AC1).** Empty input across all three buckets (no PRs opened,
  merged, or open in/at the window) → the short "nothing to report" line,
  not an empty-but-structured digest.
- **T1.6 (AC1).** A PR outside the window and not currently open (e.g.
  closed without merging, created before `since`) appears in none of the
  three buckets.

### Task 2 — `post_to_discord` + `main()`

- **T2.1 (AC2).** `post_to_discord` sends the exact formatted message as
  the JSON `content` field to the given webhook URL — verified via a
  monkeypatched `urllib.request.urlopen` capturing the request body and
  URL.
- **T2.2 (AC2).** `main()`, with `post_to_discord` monkeypatched, reads
  `SINCE`/`DISCORD_WEBHOOK_URL` from env and PR JSON from stdin, and
  returns `0` on success.
- **T2.3 (AC2).** `main()` with a missing env var (`SINCE` or
  `DISCORD_WEBHOOK_URL` unset) prints a diagnostic to stderr and returns
  non-zero rather than raising an unhandled `KeyError`.

### Task 3 — workflow inspection

- **T3.1 (AC3, AC4, AC6).** `git diff --stat` shows only
  `automation/ci/pr_digest.py`,
  `.github/workflows/pr-digest.yml`, and this slice's test/contract
  files. No literal webhook URL value anywhere in the diff — inspected
  directly. `SINCE` is `export`ed before the module invocation; `python -m
  automation.ci.pr_digest` (module form, not file-path form).

### Task 4 — live proof

- **T4.1 (AC5).** Once the secret is confirmed set: `workflow_dispatch`
  triggers the real workflow; `gh run view` shows a completed run with a
  real conclusion; Jay confirms a real message landed in Discord.
