---
phase: build
task_slug: 01-rationale-links-store
route: full
# domain_tags: 1-2 tags, ONE dominant tech surface — never every surface.
# Build retrieval is ~4 skills per contract; a 7-tag basket starves most
# surfaces (important fragments truncate, scores muddy). Keep it narrow.
domain_tags:
  - python
scope:
  touches:
    - "src/agentalloy/storage/skill_store.py"
    - "src/agentalloy/reads/rationale_links.py"
  avoids:
    - "src/agentalloy/code_index/**"
    - "src/agentalloy/retrieval/**"
    - "src/agentalloy/api/**"
success_criteria:
  - "symbol_rationale_links table added via idempotent CREATE TABLE IF NOT EXISTS, no ALTER on any existing table"
  - "rationale_for_symbol returns [] (never None, never raises) when nothing is linked"
  - "delete_skill also removes that skill's symbol_rationale_links rows"
related_contracts:
  - ".agentalloy/contracts/build/03-promote-symbol-wiring.md"
  - ".agentalloy/contracts/build/04-rationale-http-endpoint.md"
created_at: 2026-07-09T21:02:22Z
---

# 01-rationale-links-store

## Task

Add a new table to `src/agentalloy/storage/skill_store.py`'s `_SCHEMA_DDL`
(idempotent `CREATE TABLE IF NOT EXISTS`, same style as the existing
`skills`/`skill_versions`/`fragments`/`skill_dependencies` block — do not
introduce a separate migration mechanism):

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

No `REFERENCES`/FK — this codebase manages referential integrity in
application code (see `delete_skill`'s explicit cascade across 4 tables), not
via DB constraints; follow that same convention here.

Add `src/agentalloy/reads/rationale_links.py`, sibling to the existing
`src/agentalloy/reads/active.py` ("Active-version-only read queries against
the DuckDB skill store" — match its style: pure functions over a `SkillStore`,
no ORM). Two functions:

- `link_symbol(store, *, repo_slug: str, qualified_name: str, skill_id: str) -> None`
  — an idempotent upsert (re-linking the same triple is a no-op, not an error;
  DuckDB `INSERT ... ON CONFLICT DO NOTHING` or equivalent against the PK).
- `rationale_for_symbol(store, *, repo_slug: str, qualified_name: str) -> list[RationaleHit]`
  — joins `symbol_rationale_links` to `skills`/`skill_versions`/`fragments`
  (active version only, mirroring `reads/active.py`'s active-version join
  pattern) and returns each linked skill's `rationale`-type fragment content.
  `[]` when nothing is linked — never `None`, never raises.

Extend `DuckDBSkillStore.delete_skill` (`storage/skill_store.py`) with one more
explicit `DELETE FROM symbol_rationale_links WHERE skill_id = ?` in the same
cascade, same transaction, same ordering convention as its existing four
deletes.

## Test cases

From `docs/design/symbol-linked-rationale/test-plan.md`, Task 1 section:
T1.1 (AC1, link then query round-trips), T1.2 (AC4, unlinked query returns
`[]`), T1.3 (AC6, same FQN in two different repo_slugs stays isolated), T1.4
(multiple skills linked to one symbol all come back), T1.5 (AC5, no existing
table's DDL changed — only the new table is added), T1.6 (`delete_skill`
cleans up this skill's links too).

## Plan

Approach + full task order live in `docs/design/symbol-linked-rationale/`
(`approach.md` §1, `tasks.md` task 1). This is the foundation task; 03 and 04
both depend on it. Sibling is `02-symbols-line-parser` (no dependency between
them).
