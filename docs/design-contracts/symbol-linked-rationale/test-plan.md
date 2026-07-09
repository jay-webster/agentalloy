# symbol-linked-rationale — Test Plan

## Test Cases

### Task 1 — store layer

- **T1.1 (AC1).** `link_symbol(store, "repo-a", "pkg.foo", "skill-x")` then
  `rationale_for_symbol(store, "repo-a", "pkg.foo")` returns a hit for
  `skill-x` whose text matches that skill's `rationale` fragment content.
- **T1.2 (AC4).** `rationale_for_symbol` on an unlinked `(repo_slug,
  qualified_name)` returns `[]`, not `None`, not an exception.
- **T1.3 (AC6).** Link `("repo-a", "pkg.foo", "skill-x")` and
  `("repo-b", "pkg.foo", "skill-y")` (same FQN, different repos) — querying
  `("repo-a", "pkg.foo")` returns only `skill-x`; querying `("repo-b",
  "pkg.foo")` returns only `skill-y`.
- **T1.4 (design surface — multi-skill).** Two links to the same `(repo_slug,
  qualified_name)` from two different `skill_id`s both come back from one
  query call.
- **T1.5 (AC5).** After `migrate()`, inspect `agentalloy.duck`'s schema:
  `symbols`/`edges`/`skills`/`skill_versions`/`fragments` are byte-identical to
  their pre-feature `CREATE TABLE` statements (no `ALTER`); only
  `symbol_rationale_links` is new.
- **T1.6 (cleanup).** `delete_skill("skill-x")` removes its
  `symbol_rationale_links` rows too — a subsequent `rationale_for_symbol` query
  no longer returns it.

### Task 2 — `Symbols:` parser

- **T2.1.** `"Symbols: pkg.foo.Bar, pkg.baz"` → `["pkg.foo.Bar", "pkg.baz"]`
  (dots preserved, not slugified).
- **T2.2.** No `Symbols:` line present → `[]` (never falls back to deriving
  symbols from the skill id, unlike tags — there is no sensible default for a
  code symbol).
- **T2.3.** Extra whitespace / semicolon separator (`"Symbols: a.b ; c.d"`)
  parses the same as comma-separated.

### Task 3 — promotion wiring

- **T3.1 (AC1).** A lesson naming a symbol that exists in a fixture code index
  → promotion succeeds and a link row exists afterward (assert via Task 1's
  `rationale_for_symbol`, not just "no error").
- **T3.2 (AC2).** A lesson naming a symbol that does **not** exist in the
  fixture index → `action == "promoted"` still, the result includes the
  unresolved name, and no link row was created for it.
- **T3.3 (degradation).** No code index configured for the repo at all (the
  `open_code_index` call raises / has nothing for this slug) → every named
  symbol is treated as unresolved, promotion still succeeds exactly as it
  would with no `Symbols:` line at all. Verifies the optional-extra
  degradation path without needing `tree_sitter` installed (patch the
  `open_code_index` import boundary, matching the pattern the existing Piece 3
  guard test already uses for the same optional-dependency problem).
- **T3.4 (AC6).** Repo slug used for the link comes from
  `code_index.slug.repo_slug(root)` — same helper `contracts.py` already
  calls — verified by asserting the link row's `repo_slug` column matches that
  function's output for the fixture root, not a hardcoded/guessed value.
- **T3.5 (AC7).** No `lm_client`/embed import anywhere in the new code touched
  by this task (static check over the diff, mirrors the equivalent
  compound-engineering-bridge AC verification).

### Task 4 — HTTP endpoint

- **T4.1 (AC3).** `GET /symbols/{fqn}/rationale` for a linked symbol returns
  the rationale text.
- **T4.2 (AC4).** Same endpoint for an unlinked symbol returns an empty
  result (200 with `[]`, not a 404/500 — "no link" is not an error state).
- **T4.3 (AC8).** `GET /symbols/{fqn}` (the existing, pre-feature endpoint) is
  unchanged — same test fixtures that passed before this feature still pass
  identically, proving the new route is additive.
