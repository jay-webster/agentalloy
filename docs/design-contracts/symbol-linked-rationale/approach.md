# symbol-linked-rationale — Design

## Approach

### 1. The link table lives in `agentalloy.duck`, not `graph.duck` — corrected from the spec's open question

The spec left this open; reading `graph_store.py`'s own docstring resolves it in
one direction, not the other:

> "No FK constraints: edge endpoints may dangle... The graph is **derived
> data** (rebuilt from source, never migrated)... Concurrency: DuckDB is
> single-writer cross-process. Index jobs run inside the service process (**the
> service IS the code-index writer**)... out-of-process consumers open
> **read-only** or use the HTTP API."

Two consequences:

- **Ownership.** `agentalloy lessons promote` runs as a plain CLI subprocess,
  not the code-index service. Writing a link row into `graph.duck` from that
  process would break the store's own single-writer model — a genuinely new,
  unprecedented write path into an engine that explicitly reserves writes for
  itself.
- **Durability semantics.** `graph.duck` frames its own contents as
  disposable/regeneratable ("derived data... rebuilt from source"). A
  human-curated link is the opposite of that — it must survive a reindex.
  Storing it in a DB whose stated philosophy is "wipe and rebuild me" is a
  category mismatch, independent of the ownership problem above.

**Decision.** The link table, `symbol_rationale_links`, is added to
`agentalloy.duck` (the skill corpus) — the durable, authored-artifact store,
same DB `agentalloy lessons promote` already writes to. At promotion time, the
code index is consulted **read-only** (`open_code_index(settings, slug,
role="reader")` — a role the store already grants to "out-of-process
consumers", per its own docstring) purely to check that a named symbol exists;
nothing is ever written back to `graph.duck`.

This also simplifies the read path: the rationale *text* a query ultimately
returns lives in `agentalloy.duck`'s `fragments` table regardless of which DB
holds the link row, so putting the link in the same DB makes the read a single
in-process join (`symbol_rationale_links JOIN skills/fragments`), not a
cross-DB two-hop.

```sql
CREATE TABLE IF NOT EXISTS symbol_rationale_links (
  repo_slug TEXT NOT NULL,
  qualified_name TEXT NOT NULL,
  skill_id TEXT NOT NULL,
  linked_at TIMESTAMP NOT NULL,
  PRIMARY KEY (repo_slug, qualified_name, skill_id)
);
CREATE INDEX IF NOT EXISTS idx_symbol_links_lookup
  ON symbol_rationale_links(repo_slug, qualified_name);
```

No `REFERENCES`/FK to `skills(skill_id)`, matching this codebase's own existing
convention: `skill_store.delete_skill` already cascades across
`fragments`/`skill_versions`/`skill_dependencies`/`skills` via **explicit
DELETE statements in dependency order**, not `ON DELETE CASCADE` — referential
integrity is managed in application code here, not the schema. This feature
follows the same pattern (see task 4: `delete_skill` gets one more explicit
DELETE for this table, so a rolled-back or deprecated skill doesn't leave
dangling links).

### 2. `Symbols:` line: same shape as `Tags:`, without the slugification

`lesson_pack._TAGS_RE` + `_lesson_tags` already parse a `Tags:` line and
**slugify** each entry (lowercase, non-alnum → `-`). That's correct for tags,
wrong for symbols: a `qualified_name` like `agentalloy.retrieval.domain.skill_granular_select`
or a `Class.method` FQN contains dots that are load-bearing, not noise to strip.

**Decision.** A new `_SYMBOLS_RE` (identical shape, `symbols` instead of
`tags`) plus a new parse function that splits on `[,;]` and only trims
surrounding whitespace — no case-folding, no character substitution. Symbol
names are matched **exactly** against `symbols.qualified_name` (case-sensitive,
punctuation intact); no fuzzy/bare-name fallback in this slice (a design
surface question the spec deferred — exact-match-only is the simpler, more
predictable default, and AC2 already covers the "didn't resolve" path
gracefully, so a bad guess just doesn't link rather than linking to the wrong
thing).

### 3. Read path: a new `reads/` module + a new, additive HTTP endpoint

This codebase already has a convention for cross-cutting read queries against
the skill store: `src/agentalloy/reads/active.py` ("Active-version-only read
queries against the DuckDB skill store"). This feature adds a sibling,
`reads/rationale_links.py`, with one function:

```python
def rationale_for_symbol(store: SkillStore, repo_slug: str, qualified_name: str) -> list[RationaleHit]
```

`RationaleHit` = `(skill_id, rationale_text)`. Returns `[]` when nothing is
linked — never raises, never `None`-vs-`[]` ambiguity (AC4). Multiple linked
skills are all returned, unranked (spec's "Design surface" question — no
policy needed yet; a first slice doesn't need to arbitrate popularity).

The HTTP surface is a **new** endpoint, not an extension of the existing `GET
/symbols/{fqn}` response shape: `GET /symbols/{fqn}/rationale` in
`code_index/api/symbols_router.py`. Additive-only (AC5/AC8) — the existing
endpoint's response is untouched, so nothing that already parses it can break.
Internally the handler opens the skill store (read-only) and calls
`rationale_for_symbol`; it does **not** touch `graph.duck` beyond what the
existing router already does to resolve `repo_slug` for the path.

### 4. Graceful degradation when the code-index extra isn't installed

`code_index` is optional (`tree_sitter` is an extra, confirmed absent in this
dev environment — the existing Piece 3 test loads `markdown.py` standalone for
exactly this reason). Promotion must not hard-fail when the extra is missing.

**Decision.** The symbol-existence check at promotion time is wrapped: `try:
open_code_index(..., role="reader")` / `except ImportError` (or the store
being absent for that slug — no index has ever run) → treat every named symbol
as unresolved, same code path as AC2's "didn't resolve" outcome, same
warning-not-error result. `agentalloy lessons promote` on a repo with no code
index configured behaves exactly as it does today, just never links anything.

## Non-goals carried from spec

No FK/ALTER to `symbols`/`edges` (`graph.duck`) or `skills`/`fragments`
(`agentalloy.duck`) — `symbol_rationale_links` is a wholly new, additive table.
No LLM-based symbol extraction. No wiring into `code search`/`bundle`'s
automatic retrieval. No active reconciliation beyond the explicit
`delete_skill` cleanup in task 4.
