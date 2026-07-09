# symbol-linked-rationale — Tasks

## Tasks

1. **Add the `symbol_rationale_links` table + `reads/rationale_links.py`.**
   Append the new table's `CREATE TABLE IF NOT EXISTS` to `skill_store.py`'s
   `_SCHEMA_DDL` (idempotent, matches the existing pattern exactly — no new
   migration mechanism needed). Add `src/agentalloy/reads/rationale_links.py`
   with `rationale_for_symbol(store, repo_slug, qualified_name) -> list[RationaleHit]`
   and a `link_symbol(store, repo_slug, qualified_name, skill_id) -> None`
   writer, both pure functions over the store, no code-index dependency at all
   at this layer. Extend `skill_store.DuckDBSkillStore.delete_skill` with one
   more explicit `DELETE FROM symbol_rationale_links WHERE skill_id = ?`,
   matching its existing cascade-by-explicit-DELETE convention. Satisfies AC3,
   AC4, AC5 at the unit level (no promotion flow needed to test the store
   layer directly).

2. **`Symbols:` line parser.** Add `_SYMBOLS_RE` + `_lesson_symbols(text) ->
   list[str]` to `lesson_pack.py`, sibling to `_TAGS_RE`/`_lesson_tags` but
   without slugification — split on `[,;]`, strip whitespace only, preserve
   punctuation exactly. No dependency on Task 1. Satisfies the parsing half of
   AC1/AC2.

3. **Wire symbol resolution + linking into `promote_lesson`.** In
   `lessons.py`, after a successful install, call Task 2's parser on the
   lesson text; for each named symbol, attempt a **read-only** code-index
   lookup (`open_code_index(settings, repo_slug(root), role="reader")`,
   wrapped so `ImportError` or "no index for this repo" both degrade to
   "unresolved", never a hard failure) to confirm it exists in `symbols`; for
   each that resolves, call Task 1's `link_symbol`. Unresolved names are
   collected into the promotion result, not linked. Depends on Tasks 1 and 2.
   Satisfies AC1, AC2, AC6 (repo-scoping — `repo_slug` comes from the same
   `code_index.slug.repo_slug(root)` helper `contracts.py` already uses), and
   AC7 (no embed/LM call anywhere in this path — grep-checkable).

4. **`GET /symbols/{fqn}/rationale` endpoint.** New, additive route in
   `code_index/api/symbols_router.py` calling Task 1's `rationale_for_symbol`
   against the skill store (read-only) for the resolved `repo_slug` + `fqn`.
   Does not touch the existing `GET /symbols/{fqn}` handler or response shape.
   Depends on Task 1. Satisfies AC3 (HTTP-level, on top of Task 1's
   already-covered store-level AC3) and AC8 (existing endpoints/retrieval
   files untouched — a scope check on the diff, not new behavior to test).
