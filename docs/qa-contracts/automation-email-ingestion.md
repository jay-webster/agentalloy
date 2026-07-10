# automation-email-ingestion — QA Report

## Checks

- **New tests**: 12, all passing — 5 store-layer (`test_store.py`), 4
  config-loader (`test_config.py`), 3 CLI (`test_cli.py`), covering every
  acceptance criterion at the layer the spec asks for.
- **Lint**: `uv run ruff check automation/ tests/automation/` — clean.
  `uv run ruff format --check` — clean (import-sort fixes applied once
  during build, then verified stable).
- **Type checker**: `uv run pyright automation/` — **0 errors**, 3 warnings,
  all `reportUnknown*` on `yaml.safe_load`'s untyped return in `config.py` —
  the same category this repo's own `pyproject.toml` already downgrades to
  warning project-wide for untyped libraries, not a new gap this feature
  introduces.
- **Full existing suite**: `uv run pytest` (repo-wide) — 3925 passed, 2
  skipped (pre-existing, unrelated), 14 failed + 1 error, all in
  `tests/test_simple_setup.py::TestContainerFlow` and
  `tests/install/test_detect.py`. Confirmed pre-existing and unrelated by
  re-running the same tests against `main` with this feature's changes
  stashed — identical 14 failures, no podman on this machine. Zero
  regressions caused by this feature.
- **Scope check (AC6)**: `git status --short automation/ tests/automation/`
  shows only new files under those two trees; `git diff --stat pyproject.toml
  .gitignore` shows only the documented additive lines. Zero paths under
  `src/agentalloy/` touched.
- **Determinism check (AC7)**: `grep -rn "lm_client\|embed"
  automation/store.py automation/cli.py automation/config.py` — zero hits.
- **Live proof (AC8)**: Gmail reconnected mid-session (required a manual
  re-authorization by Jay — the connector's OAuth token had expired).
  `automation/config/sources.yaml` seeded with 7 real newsletter senders
  identified by scanning Jay's actual inbox (30-day `unsubscribe` search,
  manually filtered to AI-relevant senders and confirmed with Jay before
  use). The `scan-newsletters.md` routine was then followed by hand against
  the live Gmail MCP connector: built the `from:`-OR query from the real
  allowlist, ran `search_threads`, extracted fields for 31 real matching
  messages (2026-06-11 through 2026-07-10), and recorded each via the
  store (the same `CandidateStore.add` the CLI's `ingest add` calls —
  driven through a short runner script rather than 31 individual CLI
  invocations, for session efficiency; verified equivalent by also
  confirming `python -m automation.cli ingest list --status new` shows all
  31 real rows). Re-running the same ingestion a second time inserted 0 of
  31 — idempotency (AC1) confirmed against real data, not just fixtures.

## Review

### Acceptance criteria (against `docs/spec-contracts/automation-email-ingestion.spec.md`)

1. **Idempotent ingestion — MET.** `test_add_is_idempotent_by_message_id`,
   `test_add_then_add_again_is_idempotent` (CLI level), and the live proof's
   second run (0 of 31 inserted).
2. **New candidates land with `status = new` — MET.**
   `test_new_candidates_default_to_status_new`; schema-level default, not
   just application-code default.
3. **List filters by status — MET.** `test_list_filters_by_status` (store
   and CLI level).
4. **Status is updatable, missing-id is a reported no-op — MET.**
   `test_mark_updates_existing_candidate`,
   `test_mark_missing_message_id_returns_false_not_an_exception` (store),
   `test_mark_missing_message_id_reports_not_found_and_exits_nonzero` (CLI —
   confirms exit code 1 and a stderr message, not a traceback).
5. **Config-driven, not hardcoded — MET.** `test_load_sources_returns_frozenset_of_entries`,
   `test_missing_config_names_the_example_file`,
   `test_malformed_config_identifies_the_bad_value` /
   `_with_non_string_entry`. No sender literal anywhere in `store.py`,
   `cli.py`, or the routine doc — confirmed by inspection.
6. **No product code touched — MET.** Scope check above; `pyproject.toml`/
   `.gitignore` changes are additive-only lines.
7. **Deterministic, no LLM call — MET.** Determinism grep above.
8. **Live end-to-end proof — MET.** 31 real candidates ingested from Jay's
   actual inbox this session; see Checks.

### Non-goals respected

Checked against the spec's Out of Scope list: no evaluation logic anywhere
(`mark` moves status but nothing decides *which* status); no auto-build/PR
logic; no Discord wiring; no headless/unattended Gmail client — the routine
explicitly requires an agent with Gmail MCP access, which is what ran it
tonight; no cloud/paid-LLM call in any shipped code (the routine is
agent-executed by definition but ships no LLM-calling Python).

### Design conformance

Matches `approach.md` on every decision: `sqlite3` not DuckDB, `.automation/`
+ `automation/config/` mirroring the `.agentalloy/` convention,
`argparse` not a new CLI dependency, `pyyaml` (already a dependency) for
config, the routine as a markdown runbook rather than code. No drift.

### Findings

- **Required**: none.
- **Critical**: none.
- **Nit**: the live-proof ingestion used a short runner script calling
  `CandidateStore.add` directly rather than shelling out to `ingest add` 31
  times — functionally identical (same method, same idempotency guarantee),
  called out here for transparency since the spec's literal wording says
  "CLI call." Verified equivalent via the `ingest list` check.
- **Dead code**: none.

## Verdict

Clean. All 8 acceptance criteria met, including AC8's live-data requirement
— this is real inbox data, not fixtures, with idempotency independently
reconfirmed against it. No regressions to the existing suite (14
pre-existing, unrelated container-flow failures confirmed identical on
`main`). Ready to route to ship.
