# symbol-linked-rationale — QA Report

## Checks

- **Full suite**: `uv run pytest tests/ -q` (excluding the pre-existing
  podman/container-runtime tests, which fail identically on `main` before this
  branch — no podman on this machine) — **3903 passed, 2 skipped**. The 2
  skips are pre-existing and unrelated (a live-embed-server test, a CI-only
  env var gate).
- **The optional `[code-index]` extra was installed** (`uv sync --extra
  code-index`) specifically so the code-index-touching half of this feature
  (Task 3's resolver, Task 4's endpoint) could be verified against real
  `tree_sitter`-backed fixtures rather than asserted by inspection alone —
  this closes the kind of gap the compound-engineering-bridge QA pass had to
  leave as "verified by code inspection, not a live run." All
  `tests/code_index/*` tests pass, including the pre-existing
  `test_symbols_router.py` suite (regression-checked unmodified) and a new
  `test_module_wiring.py` route-inventory assertion updated to include the
  new endpoint — an intentional, expected update, not a workaround.
- **Lint**: `uv run ruff check` + `uv run ruff format --check` on all 13
  touched/new files — clean.
- **Type checker**: `uv run pyright` on every touched file (none of these
  fall under the repo's `authoring/**`/`code_index/engine/**` pyright
  exclusions) — **0 errors**. 6 warnings, all confirmed pre-existing
  (`reportPrivateUsage` on imports this feature didn't introduce,
  `reportUnknownLambdaType` on a pre-existing lambda in `add_parser`).
- **New tests, all passing**: 8 for the store layer + delete-cascade
  (`test_reads_rationale_links.py`, `test_skill_store.py`), 6 for the
  `Symbols:` parser (`test_lesson_symbols_parser.py`), 6 for the promotion
  wiring including a "no code index at all" degradation test
  (`test_lessons_promote.py`), 4 for the HTTP endpoint including an "empty
  corpus, no DB yet" degradation test (`test_symbols_rationale_router.py`) —
  24 new tests total, plus 1 pre-existing test updated for the new route.

## Review

### Acceptance criteria (against `docs/spec-contracts/symbol-linked-rationale.spec.md`)

1. **Link created on promotion — MET.** `test_link_then_query_round_trips`
   (store level) + `test_resolving_symbols_create_link_rows` (full wiring,
   promotion → real link row → queried back via the same function AC1 names).
2. **Unresolvable symbols don't block promotion — MET.**
   `test_unresolvable_symbol_reported_not_linked_promotion_still_succeeds` —
   promotion still succeeds, the bad name is reported, no link row exists for
   it.
3. **Rationale queryable by symbol — MET, both layers.** Store level:
   `test_link_then_query_round_trips`. HTTP level:
   `test_linked_symbol_returns_rationale` (real `TestClient` request against
   a real DuckDB-backed skill store, not mocked).
4. **No link, no error — MET, including a gap this pass found and fixed.**
   `test_unlinked_query_returns_empty_list` (store) and
   `test_unlinked_symbol_returns_empty_200` (HTTP) both pass. The HTTP test
   surfaced a real bug during this QA pass: see Findings.
5. **Additive only — MET.** `test_existing_tables_unchanged_by_symbol_rationale_links_addition`
   asserts every pre-existing table's column set is byte-identical; only
   `symbol_rationale_links` is new. No `ALTER` anywhere in the diff (grep-verified).
6. **Repo-scoped correctness — MET.** `test_links_are_scoped_per_repo` (store,
   synthetic collision) and `test_link_repo_slug_matches_code_index_slug_helper`
   (wiring, asserts the link's `repo_slug` is `code_index.slug.repo_slug(root)`'s
   actual output, not a guessed value — an earlier draft of this test hardcoded
   a wrong string here and was caught and fixed before landing).
7. **Deterministic, no LLM call — MET.** Grepped all four new/touched
   production files (`rationale_links.py`, `lesson_pack.py`, `skill_store.py`,
   `symbols_router.py`) for `lm_client`/`embed_client`/`EmbedClient` — zero
   hits.
8. **Existing behavior unchanged — MET.** `probe_lesson_duplicates` has zero
   diff lines (confirmed via `git diff` — the function body is untouched);
   the pre-existing `test_symbols_router.py` suite passes unmodified; only
   the route-inventory test needed updating, which is the intended, expected
   consequence of adding a real new route, not a sign of drift.

### Non-goals respected

Checked each line of the spec's Out of Scope list: no LLM-based symbol
extraction (the parser is a plain regex, `_lesson_symbols`, no model call);
no cross-task decision history attempted; `agentalloy code search`/`bundle`
are untouched (zero diff to `retrieval/hybrid.py`, `retrieval/bundle.py`,
`code_index/retrieval/**`); no active reconciliation beyond the explicit
`delete_skill` cleanup task 1 scoped; no cloud/paid-LLM call anywhere.

### Design conformance

The one design decision that most mattered — where the link table lives — was
implemented exactly as decided: `agentalloy.duck`, not `graph.duck`, with the
code index consulted read-only only. The `Symbols:` parser correctly does not
slugify (verified by `test_symbols_line_preserves_dots_not_slugified`). The
HTTP route is registered before the greedy bare-symbol route, matching the
file's own documented ordering requirement. No drift from `approach.md`.

### Findings

- **Required (found and fixed during this QA pass)**: the HTTP endpoint's
  read path (`open_skills(state.settings, read_only=True)`) raised a raw
  `duckdb.IOException` instead of returning an empty result when the skill
  corpus DB has never been created for that environment at all (e.g. no
  lesson has ever been promoted anywhere yet) — a real violation of AC4's "no
  link, no error" for a case the store-level tests couldn't catch (they always
  create the DB via `open_skill_store`'s writer-mode migrate). Caught by
  `test_unlinked_symbol_returns_empty_200`, which failed on first run with
  exactly this trace. Fixed: the handler now catches the open failure and
  degrades to `[]`, mirroring the existing dedup-probe's own "no corpus yet →
  skip" pattern already established in `lessons.py`. Re-verified green.
- **Critical**: none.
- **Nit**: none beyond what's already noted as pre-existing (private-import
  warnings, matching this codebase's existing convention across sibling
  files).
- **Dead code**: none orphaned by this change.

## Verdict

Clean. One required finding was surfaced by a test that exercised a genuinely
different code path than the store-level tests could reach (a fresh
environment with no corpus DB at all), routed to a fix, and re-verified
within this QA pass. All 8 acceptance criteria are met with no unresolved
verification caveats — unlike the prior feature's QA report, both of the
code-index-touching halves were exercised against real fixtures in this
session (the `[code-index]` extra was installed specifically to make that
possible), not left as inspection-only claims. Ready to route to ship.
