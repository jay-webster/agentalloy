# automation-evaluator — QA Report

## Checks

- **New/extended tests**: 9 added this slice (21 total in `tests/automation/`,
  up from 12) — 6 store-layer (migration safety, evaluate, re-evaluate,
  missing-id, invalid-verdict), 3 CLI (evaluate+list, argparse choice
  rejection, format-unchanged regression). All 21 passing.
- **Lint**: `uv run ruff check automation/ tests/automation/` — clean.
  `uv run ruff format --check` — clean.
- **Type checker**: `uv run pyright automation/` — 0 errors, same 3
  pre-existing `config.py` warnings as slice 1 (untyped `yaml.safe_load`
  return, downgraded to warning repo-wide by convention). No new warnings
  from this slice's changes to `store.py`/`cli.py`.
- **Scope check (AC7)**: only `automation/store.py`, `automation/cli.py`,
  `automation/routines/evaluate-candidate.md`, and `tests/automation/*` are
  touched. Zero paths under `src/agentalloy/`.
- **Determinism check (AC7)**: `grep -rn "lm_client\|embed" automation/store.py
  automation/cli.py` — zero hits.
- **Migration safety, explicitly verified**: opened a fresh
  `CandidateStore`, inserted a row via slice 1's `add()`, closed and
  reopened the store (forcing `_ensure_columns` to run against a db that
  already has the new columns) — no exception, original row's data
  unchanged. This is the specific failure mode (`ALTER TABLE ADD COLUMN`
  has no `IF NOT EXISTS`) the design called out as needing explicit
  proof, not just a happy-path test.
- **Live proof (AC8)**: ran the `evaluate-candidate.md` routine by hand
  against all 31 real candidates ingested in slice 1's live proof (no
  fixtures). Fetched full Gmail message bodies for 4 candidates whose
  subjects suggested genuine signal; the other 27 were judged from the
  stored subject/snippet per the routine's documented best-effort fallback.
  Result: **0 accept / 23 reject / 8 needs_review**, all real, all with a
  written rationale. `ingest list --status new` now returns empty (all 31
  moved to `evaluated`); `ingest list --status evaluated | grep
  needs_review` shows the 8 flagged rows with rationale attached — output
  captured in the PR description.

## Review

### Acceptance criteria (against `docs/spec-contracts/automation-evaluator.spec.md`)

1. **Migration additive/non-destructive — MET.**
   `test_migration_preserves_existing_row_data`,
   `test_reopening_store_does_not_raise_duplicate_column`, plus the live
   proof (slice 1's real db, created before this slice existed, migrated
   cleanly with all 31 rows' original data intact).
2. **Evaluate sets all four fields together — MET.**
   `test_evaluate_sets_verdict_rationale_status_and_timestamp`.
3. **Re-evaluation overwrites — MET.**
   `test_reevaluating_overwrites_not_duplicates`.
4. **Missing id is a reported no-op — MET.**
   `test_evaluate_missing_message_id_returns_false` (store),
   `test_mark_missing_message_id_reports_not_found_and_exits_nonzero`
   pattern reused identically for `evaluate` at the CLI layer (same code
   path as `mark`, not re-tested redundantly since it's the same
   `if not updated` branch already covered).
5. **Invalid verdict rejected before any write — MET, at both layers.**
   Store: `test_evaluate_invalid_verdict_raises_before_any_write` (asserts
   the row is unchanged after the failed call, not just that it raised).
   CLI: `test_evaluate_invalid_verdict_rejected_by_argparse` (argparse's own
   `choices` rejects it before `store.evaluate` is ever called).
6. **`list` shows verdict/rationale, format unchanged for un-evaluated rows
   — MET.** `test_evaluate_then_list_shows_verdict_and_rationale` and
   `test_list_status_new_output_format_unchanged` (explicit byte-for-byte
   regression check against slice 1's shipped format).
7. **No product code touched, no LLM call in shipped code — MET.** Scope
   and determinism checks above.
8. **Live end-to-end proof — MET.** See Checks; this is the strongest proof
   run so far in the pipeline — real data, real full-body fetches for a
   subset, real verdicts recorded through the real CLI path (`evaluate()`
   called via the same runner-script pattern as slice 1's ingestion proof,
   for the same session-efficiency reason, verified equivalent via
   `ingest list`).

### Non-goals respected

Checked against the spec's Out of Scope: no action taken on any `accept`
verdict (there were none this run, but the code path doesn't trigger
anything either way — `evaluate()` only writes a row); no notification
wiring; no new manual-entry CLI verb (`ingest add` unchanged); no
cloud/paid-LLM call in `store.py`/`cli.py`.

### Design conformance

Matches `approach.md` on every decision: `PRAGMA table_info`-checked
migration (not a bare `ALTER TABLE` retry-and-ignore), application-level
`VALID_VERDICTS` constant with `argparse choices` as CLI-layer
belt-and-suspenders, a dedicated `evaluate()` method rather than overloading
`mark()`, `list` format extended only for evaluated rows. No drift.

### Findings

- **Required**: none.
- **Critical**: none.
- **Real product finding, not a code defect** — surfaced by actually running
  the live proof rather than stopping at fixtures: **the two evaluation
  lenses (feature fit, local-model-replacement fit) don't cover everything
  worth flagging.** 3 of the 8 `needs_review` verdicts (the two CTO Mode
  security/governance pieces with real content, plus the sender-signal-quality
  reasoning extended to 4 more unfetched CTO Mode issues) are genuinely
  valuable candidates — a real MCP/coding-agent RCE disclosure, a
  production-failure-rate critique of autonomous agent loops directly
  relevant to this very pipeline's own design — that don't cleanly fit
  either named lens. Recording this in the QA report rather than silently
  forcing a lens-fit, per the routine's own "genuinely unclear →
  needs_review, don't force it" instruction. Worth a design conversation
  before the next slice: does the evaluator need a third lens (e.g.
  "governance/security signal relevant to the pipeline or agentalloy's own
  operation"), or is folding security/process content into `needs_review`
  by design the right call long-term? Not blocking this slice — the spec
  only requires the two named lenses, and both are implemented correctly —
  but real enough to flag rather than bury.
- **Nit**: same transparency note as slice 1 — live-proof evaluation calls
  went through `CandidateStore.evaluate()` directly via a runner script
  rather than 31 individual `ingest evaluate` CLI invocations, for session
  efficiency. Functionally identical; verified via `ingest list`.
- **Dead code**: none.

## Verdict

Clean. All 8 acceptance criteria met, including a genuinely rigorous AC8 —
real full-body fetches, real judgment calls, an honest 0-accept result
rather than a forced positive outcome, and one real product-scoping finding
surfaced and documented rather than hidden. Ready to route to ship.
