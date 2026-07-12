# Automation PR Digest

> **Scope in a sentence.** A scheduled GitHub Actions workflow that posts a
> regular Discord digest of PR activity (opened, merged — noting auto vs.
> manual, still open) so Jay has visibility without checking GitHub
> himself, especially once low-risk PRs start merging themselves.

> **Location note.** At runtime the SDD spec phase writes the spec to
> `docs/spec/automation-pr-digest.md`, git-ignored. This file is the
> committed, reviewable copy.

## Context

Jay's explicit ask, in response to being told what enabling GitHub's
auto-merge settings would (and wouldn't) do: pushing/opening PRs should
stay exactly as manual as it is today, but he wants **a digest of work at
regular intervals, with a description of the PR and the merge** — so
auto-merged PRs (and PR activity generally) don't just silently happen
somewhere he isn't watching.

A Discord digest mechanism already exists (`automation-discord-notify`,
PR #7) but it's scoped to candidate-evaluation results (accept/reject/
needs_review counts from the newsletter pipeline) — a different concern
entirely, and its actual delivery (`curl` from inside a scheduled
`RemoteTrigger` cloud-agent routine) is unfinished (task 31 is still
blocked on Jay providing a webhook URL, per that slice's own QA report).

This slice's subject — PR/CI activity — is pure GitHub-side data with no
dependency on Gmail, Drive, or the candidate store. It doesn't need a
cloud-agent routine at all: GitHub Actions' native `schedule` trigger
(cron) can run entirely inside this repo's own CI, the same
already-proven-live infrastructure `gemini-review.yml` and
`auto-merge-gate.yml` use. This is architecturally simpler than the
newsletter pipeline's Gmail/Drive bridge, which existed specifically
because Gmail wasn't available as a `RemoteTrigger` connector — that
constraint doesn't apply here.

## Assumptions (correct these before design)

- **A new, separate mechanism, not an extension of `automation-discord-
  notify`.** Different data source (GitHub API vs. the candidate sqlite
  store), different trigger (GitHub Actions `schedule` vs. a
  `RemoteTrigger` cloud routine), different concern (code/PR activity vs.
  newsletter-candidate evaluation). Sharing a Discord *channel* is fine;
  sharing *code* isn't warranted by anything the two actually have in
  common.
- **A new GitHub Actions secret**, e.g. `DISCORD_WEBHOOK_URL` — Jay
  creates the webhook in his own Discord server and sets it as a repo
  secret himself, exactly the `GEMINI_API_KEY` pattern: never pasted into
  chat, verified only via the workflow run's real outcome.
- **Stateless rolling window, not persisted "since last run" state.** Each
  scheduled run reports on activity from "now minus the schedule
  interval" (e.g., the last 24 hours for a daily cron) — computed fresh
  each run from the current time, no database or state file needed. This
  is deliberately simpler than the candidate-store digest's `evaluated_at
  >= since` pattern, which has persisted state (the sqlite db) to query
  against; this slice has none, and shouldn't invent any just to track
  "since when."
- **Distinguishing auto-merge from manual merge is a real, useful, but
  best-effort signal, not a hard guarantee.** `gh pr view --json
  mergedBy` returns a user object with an `is_bot` field — confirmed live
  against PR #9 (`mergedBy.is_bot: false`, Jay's own manual merge). The
  design's working assumption is that a PR merged via `gh pr merge --auto`
  under the workflow's own `GITHUB_TOKEN` will show `is_bot: true` /
  `login: "github-actions[bot]"` — **not yet confirmed against a real
  auto-merged PR**, since none exists yet (that only becomes possible
  once `automation-auto-merge-gate`'s settings checkpoint is live). Design
  should make this an isolated, clearly-labeled heuristic that degrades
  gracefully (e.g. "merged" with no auto/manual label) rather than
  something the whole feature depends on being right.

## What

**Pure formatting function**, `automation/ci/pr_digest.py`: takes a list of
PR records (as returned by `gh pr list --json ...`) and a `since`
timestamp, and produces a Discord-message-formatted digest: PRs opened in
the window (title + link + author), PRs merged in the window (title +
link, labeled auto-merged or manually-merged per the heuristic above), PRs
still open (title + link, count). No activity in the window → a short
"nothing to report" line, not a wall of zeros (same principle
`automation-discord-notify` already established).

**Isolated impure delivery function**: posts the formatted digest to a
Discord webhook URL via `urllib.request` (same dependency-free approach as
`gemini_review.py`'s `call_gemini` — no new pip dependency), reading the
URL from an environment variable. Fully monkeypatchable in tests, same
pattern as every prior external-integration slice tonight.

**New scheduled workflow**, `.github/workflows/pr-digest.yml`: `schedule`
(cron) plus `workflow_dispatch` for manual/live-proof runs. Computes the
time window, fetches real PR data via `gh pr list --json ...`, pipes it
through the new script (invoked as `python -m automation.ci.pr_digest` —
module invocation from the start, per the real bug found and fixed in
`auto-merge-gate.yml`'s own first live run), which formats and posts.

## Acceptance Criteria

1. **The formatting function correctly buckets PRs into
   opened/merged/still-open and renders each with title, link, and (for
   merged) an auto/manual label when determinable.** Verifiable by unit
   tests against fixture PR-record lists covering all three buckets plus
   the empty-window case.
2. **The delivery function posts the exact formatted text to the webhook
   URL, and only reads the URL from an environment variable — never a
   literal value anywhere in committed code.** Verifiable by a unit test
   monkeypatching the HTTP call, plus a scope/grep check.
3. **The workflow computes its time window and fetches real PR data
   correctly, then pipes it through the script via module invocation.**
   Verifiable by code review plus live proof (AC5).
4. **No product code touched.** Zero diff under `src/agentalloy/`; zero
   diff to any existing workflow or automation file (this is new, parallel
   infrastructure, not a modification of `automation-discord-notify`'s
   candidate-digest code).
5. **Live proof.** Once Jay confirms `DISCORD_WEBHOOK_URL` is set as a
   repo secret: trigger the workflow for real (via `workflow_dispatch` —
   no need to wait for the cron schedule to fire), confirm a real message
   lands in Jay's Discord channel, inspected via the workflow run's
   conclusion (GitHub redacts the secret from logs automatically — this
   session never sees or needs to see the raw webhook URL, same discipline
   as the Gemini key).
6. **No new external credential exposure.** Same bar as every prior
   slice — the webhook URL is a secret Jay provisions and owns, never
   pasted into chat or committed.

## Out of Scope

- **Modifying `automation-discord-notify` or its candidate-evaluation
  digest.** Fully separate concern, fully separate code path.
- **Persisted "since last successful run" tracking.** Stateless rolling
  window only (see Assumptions) — if a run is missed (e.g. a transient
  Actions outage), that window's activity is simply not reported, not
  retroactively caught up. Acceptable given the low stakes of a
  visibility digest, not worth the complexity of real state tracking.
- **CI check status/failure reporting.** This digest is about PR
  lifecycle (opened/merged/open), not about individual check pass/fail —
  Gemini's own PR comments and GitHub's PR UI already surface that.
- **Guaranteeing the auto-vs-manual merge label is always correct.** It's
  a best-effort heuristic (see Assumptions), not a hard guarantee — a
  wrong or missing label is a cosmetic gap, not a functional one.
- **Any change to the GitHub settings from `automation-auto-merge-gate`**
  (branch protection, `allow_auto_merge`). Fully independent — this slice
  ships and can be live-proofed with only manually-merged PRs; it doesn't
  need auto-merge to actually be enabled to be useful or testable.

## Design surface (hand-off to the design phase)

- **Schedule interval**: Jay said "regular intervals" without specifics.
  Design proposes a sensible default (daily, at a fixed UTC time) with
  `workflow_dispatch` always available for on-demand runs; Jay can adjust
  the cron expression trivially later if a different cadence is wanted.
- **Message format**: plain text (matching `automation-discord-notify`'s
  precedent — "nothing in the real proof output needed structure beyond
  what plain text with a blank-line-separated layout already gives") vs.
  a Discord embed. Design confirms; lean toward plain text for
  consistency and because it already worked for the other digest.
