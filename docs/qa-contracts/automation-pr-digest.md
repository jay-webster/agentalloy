# automation-pr-digest — QA Report

## Checks

- **New tests**: 11 added (`test_pr_digest.py`) — PR created in window →
  opened bucket; PR merged in window → merged bucket; currently-open PR →
  still-open bucket regardless of age; bot merger → "auto-merged" label;
  human merger → "manually merged" label; missing merger → bare "merged"
  label; all-empty buckets → short "nothing to report" line; a PR outside
  the window and not open → appears in no bucket; `post_to_discord` sends
  the exact `{"content": ...}` body to the given URL (monkeypatched
  `urlopen`); `main()` returns 0 on a monkeypatched success path; `main()`
  with a missing env var returns non-zero with a stderr diagnostic
  naming the missing var, not a raw `KeyError`. **90 total in
  `tests/automation/`** (79 pre-existing + 11 new), all pass unmodified.
- **Lint**: `uv run ruff check .` — clean, whole repo. `uv run ruff format
  --check .` — clean, whole repo.
- **Type checker**: `uv run pyright automation/ci/` — **0 errors**. The
  10 warnings present are the same pre-existing untyped-external-data
  category on `gemini_review.py` already accepted in that slice's own QA
  report — nothing new from this slice's files.
- **Module-invocation check, applied preemptively**: ran the exact CI
  invocation locally before trusting it —
  `echo '[]' | SINCE=... DISCORD_WEBHOOK_URL=... uv run python -m
  automation.ci.pr_digest` — confirmed it resolves the `automation.*`
  import correctly (no `ModuleNotFoundError`, the real bug found live in
  `auto-merge-gate.yml`'s first run) and fails only for the expected
  reason (a deliberately fake webhook domain in the test invocation,
  producing the intended error-handling path, not a crash).
- **Scope check (AC4)**: `git status --short` on this branch shows exactly
  three new files: `automation/ci/pr_digest.py`,
  `tests/automation/ci/test_pr_digest.py`,
  `.github/workflows/pr-digest.yml`. Zero diff to `src/agentalloy/`, zero
  diff to `automation-discord-notify`'s code
  (`automation/store.py`/`automation/cli.py`), zero diff to any
  pre-existing workflow file.
- **Secret-handling check (AC6)**: `grep -rn "discord.com/api/webhooks\|DISCORD_WEBHOOK_URL.*=.*['\"]"`
  across the new files — zero hits. The workflow references
  `secrets.DISCORD_WEBHOOK_URL` only; the script reads
  `os.environ["DISCORD_WEBHOOK_URL"]` only. No webhook value has appeared
  in this session's conversation or any file.
- **Live proof (AC5)**: **not yet reached.** Blocked on Jay confirming
  `DISCORD_WEBHOOK_URL` is set as a repo secret — the same still-open
  dependency `automation-discord-notify`'s task 31 has been waiting on.
  Will be recorded here once performed.

## Review

### Acceptance criteria (against `docs/spec-contracts/automation-pr-digest.spec.md`)

1. **Formatting function correctly buckets and labels — MET.** See
   Checks, new tests T1.1-T1.6.
2. **Delivery function posts correctly, URL only from env — MET.** See
   Checks, T2.1-T2.3.
3. **Workflow computes its window and fetches real PR data via module
   invocation — MET** (code review) **, live-run confirmation NOT YET
   REACHED** (AC5).
4. **No product code touched — MET.** See Checks, scope check.
5. **Live proof — NOT YET REACHED.** Blocked on Jay setting
   `DISCORD_WEBHOOK_URL`.
6. **No new external credential exposure — MET.** See Checks,
   secret-handling check.

### Non-goals respected

Checked against the spec's Out of Scope: `automation-discord-notify`'s
code is completely untouched; no persisted since-last-run state added
(stateless rolling window only); no CI check-status reporting added (PR
lifecycle only); the auto/manual merge label is explicitly documented as
best-effort, not guaranteed; no GitHub settings from
`automation-auto-merge-gate` touched by this slice.

### Design conformance

Matches `approach.md` on every decision: pure `format_digest` +
`_merge_label` split (§1-2); `post_to_discord` isolated exactly like
`gemini_review.py`'s `call_gemini` (§3); every env-var read inside
`main()`'s `try` from the start, not discovered live a second time (§4);
`gh pr list` with no `--repo` flag, `SINCE` exported as a real shell env
var, module-form invocation (§5); daily 13:00 UTC cron plus
`workflow_dispatch` (§6); plain-text message (§7).

### Findings

- **Critical**: none.
- **Dead code**: none.
- **Real gap avoided by applying a prior slice's lesson preemptively**:
  the exact `ModuleNotFoundError` class of bug that required a live CI
  failure to discover in `auto-merge-gate.yml` was caught here *before*
  pushing, by deliberately running the exact CI invocation locally first
  (see Checks). This is direct evidence the "apply prior findings
  preemptively" discipline this session has been building actually pays
  off, not just a retrospective lesson-doc entry.
- **Deliberately incomplete, not a defect**: AC5 (live proof) is blocked
  on Jay's action (setting the webhook secret), named explicitly rather
  than silently deferred — matching `automation-discord-notify`'s own
  precedent for the identical kind of external-dependency gap.

## Verdict

**Partial — clean for what's in scope of this PR.** ACs 1, 2, 4, 6 are
fully met with real test coverage and direct inspection; AC3 is met by
code review with live confirmation pending. AC5 is honestly incomplete,
blocked on Jay providing a Discord webhook URL — the same real, unresolved
dependency `automation-discord-notify`'s own task 31 has been sitting on.
Not silently glossed over. This PR is safe to merge on its own: the new
workflow is inert (a `schedule`/`workflow_dispatch`-triggered job with no
effect on merges, branch protection, or any existing workflow) until the
secret is set and a live run is performed.
