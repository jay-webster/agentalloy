# automation-discord-notify — QA Report

## Checks

- **New tests**: 7 added to `test_cli.py` — `since` filter correctness
  (T1.1), verdict-tiered detail level with an explicit negative assertion
  that reject's message_id/rationale never appear in body text (T1.2),
  empty-window short statement (T1.3), all-rejected-window short statement
  with no section headers (T1.4), flagged mention present (T1.5) and
  absent (T1.6). All of slices 1-5's existing 48 tests still pass
  unmodified. **54 total in `tests/automation/`.**
- **Lint**: `uv run ruff check automation/ tests/automation/` — clean.
  `uv run ruff format --check` — clean.
- **Type checker**: `uv run pyright automation/` — **0 errors**, 9
  warnings, all pre-existing categories (untyped external data from
  `json.loads`/`yaml.safe_load`, already downgraded to warning repo-wide).
  No new warning categories from `report`'s own code.
- **Scope check (AC5)**: `git status --short` shows only `automation/cli.py`
  (modified), `automation/routines/scheduled-drive-sync.md` (modified),
  and `tests/automation/test_cli.py` (modified). Zero paths under
  `src/agentalloy/`.
- **Determinism check (AC5)**: `grep -rn "lm_client\|embed" automation/cli.py`
  — zero hits. `report` uses only stdlib (list comprehensions, f-strings);
  no new dependency.
- **Live proof (AC6)**: ran `uv run python -m automation.cli ingest report
  --since "2026-07-10T00:00:00Z"` against the real production database (39
  real, already-evaluated candidates from the last two sessions). Output:
  "39 evaluated (0 accept, 9 needs_review, 30 reject)", followed by full
  detail for all 9 `needs_review` candidates (message_id, source, subject,
  rationale each) and no itemized detail for any of the 30 `reject`
  candidates. Matches exactly what's already known and recorded in
  project memory from those two sessions' real evaluation work — a strong
  correctness signal, since this is independent verification against data
  this slice's own code had no role in producing.
- **Webhook delivery + live routine update (AC7): not yet completed.**
  Blocked on Jay providing a Discord webhook URL — same shape as slice 5's
  Apps Script deployment being a Jay-side follow-up action after the PR
  shipped. Task 31 remains open until that happens; this QA report will be
  the reference point for closing it out, not a blocker for shipping the
  tested, working half now.

## Review

### Acceptance criteria (against `docs/spec-contracts/automation-discord-notify.spec.md`)

1. **`since` filter correctness — MET.** `test_report_filters_by_since`
   plus the live proof (correctly excludes nothing outside the given
   window against real timestamped data).
2. **Verdict-tiered detail — MET.** `test_report_verdict_tiered_detail`
   explicitly asserts reject's message_id and rationale text do NOT appear
   in the output — not just that accept/needs_review's do.
3. **Empty and all-rejected windows are short statements — MET.**
   `test_report_empty_window_is_short`,
   `test_report_all_rejected_window_is_short` (also asserts no `ACCEPT:`/
   `NEEDS REVIEW:` headers appear for the all-rejected case).
4. **Flagged mention is conditional and count-only — MET.**
   `test_report_flagged_mention_present_when_applicable`,
   `test_report_flagged_mention_absent_when_zero`.
5. **No product code touched, no new dependency, no LLM call — MET.**
   Scope and determinism checks above.
6. **Live proof of the testable half — MET.** See Checks — real command,
   real 39-candidate production database, output cross-checked against
   independently-recorded memory of what that data should show.
7. **Webhook delivery + explicit-confirmation routine update — NOT YET
   MET.** Blocked on Jay's webhook URL, which only he can create. Will be
   completed and this report will note the outcome once available — not
   silently skipped or claimed done early.

### Non-goals respected

Checked against the spec's Out of Scope: no other notification channel
implemented; no two-way Discord interaction; no message-length
truncation logic added (not needed at the real 9-item digest size just
proven); the evaluator's own logic (`evaluate-candidate.md`,
`CandidateStore.evaluate`) is completely untouched by this slice — `report`
only reads already-recorded verdicts.

### Design conformance

Matches `approach.md` on every decision: plain-text Discord payload (no
embeds — nothing in the real proof output needed structure beyond what
plain text with a blank-line-separated layout already gives); `SINCE`
captured before the evaluation step, not after (verified by inspection of
the routine doc's step ordering); the webhook URL appears in the routine
doc only as an explicit placeholder string, never a real value (verified
by inspection — the literal text `<DISCORD_WEBHOOK_URL>` is what's
committed).

### Findings

- **Required**: none in the shipped code.
- **Critical**: none.
- **Nit**: AC7 is genuinely incomplete pending an external dependency (Jay's
  webhook URL) — flagged explicitly above rather than glossed over, matching
  this session's standing practice for gaps that are real and unavoidable
  at ship time (same treatment slice 5 gave the Apps Script deployment).
- **Dead code**: none.

## Verdict

Clean for the testable half — 6 of 7 acceptance criteria fully met, with a
strong live-proof cross-check against independently-known real data. AC7
is honestly incomplete, blocked on Jay's action, not silently deferred.
Ready to route to ship for the code; task 31 (webhook delivery + live
routine update) follows as soon as the URL is available.
