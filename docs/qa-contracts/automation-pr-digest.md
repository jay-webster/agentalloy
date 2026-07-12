# automation-pr-digest — QA Report

## Checks

- **New tests**: 12 added (`test_pr_digest.py`) — PR created in window →
  opened bucket; PR merged in window → merged bucket; currently-open PR →
  still-open bucket regardless of age; bot merger → "auto-merged" label;
  human merger → "manually merged" label; missing merger → bare "merged"
  label; all-empty buckets → short "nothing to report" line; a PR outside
  the window and not open → appears in no bucket; `post_to_discord` sends
  the exact `{"content": ...}` body to the given URL (monkeypatched
  `urlopen`); `main()` returns 0 on a monkeypatched success path; `main()`
  with a missing env var returns non-zero with a stderr diagnostic
  naming the missing var, not a raw `KeyError`; `main()` with an empty
  (present-but-blank) `DISCORD_WEBHOOK_URL` skips gracefully with exit 0,
  never calling `post_to_discord`. **91 total in `tests/automation/`**
  (79 pre-existing + 12 new), all pass unmodified.
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
- **First real review pass returned `request_changes` — one finding
  investigated and rejected as factually incorrect, one acknowledged as
  already-deliberate scope.**
  1. **Claimed major, investigated, rejected**: Gemini claimed `gh pr
     list --json mergedBy` returns camelCase `isBot`, not the snake_case
     `is_bot` this code checks — which would make every bot-merge
     silently mislabeled "manually merged." **Checked directly against
     real live data**: `gh pr view 9 --json mergedBy` and `gh pr list
     --json number,mergedBy` (against PRs #9, #10, #11, all real,
     already-merged PRs on this repo) both return `is_bot` in snake_case,
     exactly matching this code's field name. This is the same field
     name already verified once before, during this slice's own design
     phase, against the same PR #9. **Not fixed — there is nothing to
     fix.** This is the first finding across five real Gemini review
     rounds this session where the finding itself, not the code, was
     wrong — worth recording plainly rather than either silently
     "fixing" correct code or silently ignoring a `request_changes`
     verdict.
  2. **Claimed minor, real, already-deliberate**: Discord's 2000-character
     message limit could theoretically be exceeded at high PR volume.
     This exact risk was already named and deliberately deferred in this
     slice's own spec ("Out of Scope: ... no message-length safeguard...
     not worth the complexity... at the real 9-item digest size just
     proven" — direct precedent from `automation-discord-notify`'s spec,
     restated here). Not a new finding requiring a new decision — Gemini
     independently arrived at a risk this slice's spec had already
     weighed and consciously accepted.
- **Second real review pass — the `isBot` claim repeated (still
  incorrect, still not fixed — see above), but a second finding this
  round was new, real, and fixed.** `main()` treated
  `DISCORD_WEBHOOK_URL` as present-or-KeyError, but the workflow always
  passes `secrets.DISCORD_WEBHOOK_URL` as an env var regardless of
  whether the secret is actually set — before Jay sets it, that resolves
  to an **empty string**, not a missing key, so the old code would reach
  `post_to_discord` and crash on `urllib.request` with an empty URL. Since
  this workflow runs on a daily schedule starting the moment it's merged
  — well before the live-proof step that provisions the real secret — this
  would have produced a real failure email every single day until Jay
  got to it. **Fixed**: `main()` now checks for an empty (not just
  missing) `webhook_url` and exits `0` with a clear log line instead of
  attempting delivery. Covered by
  `test_main_empty_webhook_url_skips_gracefully`.
- **Live proof (AC5), performed after merge, found one real bug.** Jay
  created a real Discord webhook and set `DISCORD_WEBHOOK_URL` as a repo
  secret (confirmed via `gh secret list`, value never seen by this
  session). First real `workflow_dispatch` run: `HTTP Error 403:
  Forbidden` posting to Discord — the error-handling correctly printed a
  diagnostic and exited non-zero rather than crashing silently, exactly
  as designed. Root cause: `post_to_discord` sent no `User-Agent` header,
  so `urllib.request` used its default `Python-urllib/x.y` string, which
  Discord's edge (Cloudflare) is known to reject with a bare 403 for
  requests lacking a real user agent. **Fixed**: added an explicit,
  identifiable `User-Agent` header (`agentalloy-pr-digest/1.0`). Covered
  by a new assertion in `test_post_to_discord_sends_content_field_to_webhook_url`
  confirming the header isn't the default urllib string. Fixed and merged
  as PR #13.
- **Second real `workflow_dispatch` run, after PR #13 merged: full
  success, confirmed end-to-end.** `gh run view` showed `conclusion:
  success`; the run's own log showed a correctly formatted real digest —
  8 opened, 8 merged (PRs #6-#13, all real, all labeled "manually
  merged" since no auto-merge has happened yet); **Jay confirmed the
  message actually arrived in his Discord channel.** AC5 is fully met.

## Review

### Acceptance criteria (against `docs/spec-contracts/automation-pr-digest.spec.md`)

1. **Formatting function correctly buckets and labels — MET.** See
   Checks, new tests T1.1-T1.6.
2. **Delivery function posts correctly, URL only from env — MET.** See
   Checks, T2.1-T2.3.
3. **Workflow computes its window and fetches real PR data via module
   invocation — MET.** Confirmed by a real, successful `workflow_dispatch`
   run producing a correctly formatted digest.
4. **No product code touched — MET.** See Checks, scope check.
5. **Live proof — MET.** A real Discord webhook, a real repo secret, two
   real `workflow_dispatch` runs (one surfacing and fixing a genuine
   `403` bug, one succeeding end-to-end), and Jay's direct confirmation
   the message landed in his Discord channel.
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
- **Real bug, found in live proof and fixed (PR #13)**: `post_to_discord`
  sent no `User-Agent` header, so Discord's Cloudflare edge rejected the
  request with a bare `403` — invisible to every unit test (which
  monkeypatches `urlopen` entirely) and only catchable by a real POST to
  a real Discord endpoint. Direct validation of AC5's own purpose.

## Verdict

**Clean — all 6 acceptance criteria met, with a real bug found and fixed
along the way.** ACs 1, 2, 4, 6 were met with real test coverage and
direct inspection from the start. AC3 and AC5 required Jay's real
Discord webhook and repo secret to complete — once provided, live proof
found one genuine bug (Discord's `403` on urllib's default User-Agent,
fixed in PR #13) that no unit test could have caught, then succeeded
cleanly on a second real run, confirmed by Jay seeing the actual message
in his Discord channel. The `review` check's one `fail` state during
this slice's history was investigated and traced to a factually
incorrect claim in Gemini's review (see Checks) — the code's field name
was verified correct against real, live GitHub data — not a real defect,
and documented rather than either blindly "fixed" or silently ignored.
