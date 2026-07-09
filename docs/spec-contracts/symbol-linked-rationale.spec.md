# Symbol-Linked Rationale — Spec

> **Scope in a sentence.** When a promoted lesson names the code symbols its
> rationale explains, record that link so a future lookup of that symbol can
> surface *why* it's the way it is — the first slice of the Knowledge module's
> "decisions graph linking rationale to symbols," deferred by
> `compound-engineering-bridge`'s Out of Scope.

> **Location note.** At runtime the SDD spec phase writes the spec to
> `docs/spec/symbol-linked-rationale.md`, git-ignored. This file is the
> committed, reviewable copy.

## Context

`agentalloy lessons promote <slug>` (shipped) already turns a
`docs/solutions/<slug>.md` lesson into an installed domain skill with an
`execution`/`verification`/`rationale` fragment split. That skill is retrievable
by the signal layer at compose time and by free-text search — but nothing ties
it to the *specific code* the rationale is about. If a lesson explains why
`retrieval/domain.py`'s `skill_granular_select` takes a keyword-only signature,
today the only way to find that lesson from the symbol is to already know it
exists and search for it by guessed keywords.

Two engines already exist and stay separate, confirmed by reading the code:

- **Code index** (`graph.duck`, per-repo-slug): a `symbols` table keyed by
  `qualified_name` (FQN), with `callers`/`callees`/`transitive_callers` queries
  already exposed via `GET /symbols/{fqn}` and `agentalloy code search`/`bundle`.
- **Skill corpus** (`agentalloy.duck`, single shared instance): `skills` /
  `skill_versions` / `fragments`, where `fragments.content` is free-text prose —
  no column anywhere stores a file path or symbol FQN in structured form.

They are genuinely separate DuckDB files (`code_index_data_dir` vs
`duckdb_path`, `config.py`), and both stores' docstrings independently note
DuckDB's single-writer-cross-process locking constraint — there is no existing
mechanism, and no existing seam (`grep` for `code_index` in `signals/`,
`retrieval/`, `ingest.py` returns zero hits) to cross them.

## Assumptions (correct these before design)

- This applies to **promoted skills only** (skill_id + fragment content already
  exist in `agentalloy.duck`), not raw, unpromoted `docs/solutions/` lessons —
  consistent with promotion already being the deliberate curation step
  (`compound-engineering-bridge` Piece 2).
- Symbol identification is **author-declared, not LLM-extracted** — consistent
  with "deterministic by default." A lesson names its symbols explicitly (e.g. a
  `Symbols:` line, mirroring the existing `Tags:` convention already parsed by
  `lesson_pack.py`'s `_TAGS_RE`/`_lesson_tags`), not inferred by scanning prose
  for anything that looks like an identifier.
- A link is scoped to **one repo** (`repo_slug`) — `qualified_name` alone is not
  globally unique across repos wired to the same shared skill corpus.
- Enforcement is best-effort, not transactional: the two DBs are separate files
  with no cross-file FK. A link whose symbol was renamed/removed, or whose skill
  was deprecated, can go stale; this spec does not require active reconciliation
  (see Out of Scope).

## What

**Write path.** When `agentalloy lessons promote <slug>` runs, if the lesson
declares symbols it explains (`Symbols:` line, comma/semicolon-separated FQNs or
short names), and the promotion succeeds, record a link per named symbol:
`(repo_slug, qualified_name) -> skill_id`. A symbol name that doesn't resolve
against the current code index (typo, wrong repo, stale rename) is dropped with
a warning in the promotion result, not a hard failure — promotion of the skill
itself must not be blocked by an unresolvable symbol reference.

**Read path.** A new query function (and a thin CLI/API surface proving it's
real, per the acceptance criteria) that, given `(repo_slug, qualified_name)`,
returns the linked skill(s)' `rationale` fragment content — empty/`None` when
nothing is linked, never an error.

**Storage.** A new, additive table/store for the link rows — no schema change to
either existing engine's tables. Exact placement (which DB file, or a small
third one) is a design decision (see Design surface).

## Acceptance Criteria

1. **Link created on promotion.** Promoting a lesson with a `Symbols:` line
   naming a symbol that exists in the target repo's code index creates a
   queryable link row for `(repo_slug, qualified_name, skill_id)`. Verifiable by
   a unit test: promote a lesson naming a real (fixture) symbol, assert the link
   query returns that skill_id.
2. **Unresolvable symbol names don't block promotion.** A `Symbols:` entry that
   doesn't match anything in the code index is dropped (not linked) and the
   promotion result reports it; the skill still installs normally. Verifiable by
   a test asserting `action == "promoted"` with an unresolved-symbols list in the
   result, and no link row created for the bad name.
3. **Rationale is queryable by symbol.** Given a linked `(repo_slug,
   qualified_name)`, the new query function returns the skill's `rationale`
   fragment content. Verifiable by a unit test asserting the returned text
   matches the promoted skill's rationale fragment.
4. **No link, no error.** Querying a symbol with no linked skill returns
   empty/`None`, not an exception. Verifiable by a test against an unlinked
   fixture symbol.
5. **Additive only — no existing schema changed.** No `ALTER TABLE` on
   `skills`/`skill_versions`/`fragments` (`agentalloy.duck`) or `symbols`/`edges`
   (`graph.duck`); the link lives in its own table. Verifiable by inspecting the
   migration/DDL the feature adds.
6. **Repo-scoped correctness.** A link created against repo A's `qualified_name`
   never surfaces when querying the same `qualified_name` string under repo B.
   Verifiable by a test with two fixture repo slugs sharing a colliding FQN.
7. **Deterministic, no LLM call.** Neither link creation nor the query path
   calls an embed/LM client. Verifiable by code inspection (no `lm_client`/embed
   import in the new module) — consistent with `compound-engineering-bridge`'s
   equivalent AC.
8. **Existing behavior unchanged.** `agentalloy code search`/`code bundle` and
   `agentalloy lessons promote`'s existing dedup-probe/install behavior are
   unmodified by this feature (this is additive, not a retrieval rewrite).
   Verifiable: no diff to `retrieval/hybrid.py`, `retrieval/bundle.py`, or the
   pre-ingest dedup probe in `install/subcommands/lessons.py`.

## Out of Scope

- **Automatic (LLM-based) symbol extraction** from lesson prose. Explicit
  author declaration only, this slice.
- **Cross-task decision history** — chaining multiple lessons that touched the
  same symbol/file over time into a sequence. A real feature, deliberately a
  *different* slice (see the sibling option not chosen today), not folded in
  here to keep this one shippable.
- **Injecting linked rationale into `agentalloy code search`/`bundle`
  results automatically.** This spec ships the data model and a proof-it-works
  query surface; wiring it into the code-index's own retrieval/compose path so
  an agent sees it unprompted is a follow-on decision (it mixes the two
  engines' retrieval concerns and deserves its own spec).
- **Active reconciliation** of stale links (renamed/removed symbols, deprecated
  skills). Lazy/best-effort only.
- **Any cloud or paid-LLM call.**

## Design surface (hand-off to the design phase)

- **Where the link table lives.** A new table inside `agentalloy.duck`
  (alongside `skills`/`fragments`, referencing `graph.duck`'s `qualified_name`
  by string only, no cross-file FK), a new table inside each repo's `graph.duck`
  (referencing `skill_id` by string only), or a small standalone third store.
  Trade off write locality (promotion writes to the skill corpus already) against
  query locality (symbol lookups originate from the code-index side).
- **`Symbols:` line parsing.** Reuse `lesson_pack._TAGS_RE`'s pattern shape for a
  `Symbols:` line, or a distinct convention if FQNs need punctuation `Tags:`
  doesn't (`.`, `::`, generic brackets) — check what `qualified_name` actually
  looks like for the languages this repo's code index parses.
  Also: match against `symbols.qualified_name` (exact) or also fall back to bare
  `name` when the FQN doesn't resolve (usability vs. precision).
- **Query surface shape.** Extend `GET /symbols/{fqn}` to include linked
  rationale directly, or a new endpoint (`GET /symbols/{fqn}/rationale`) plus a
  new CLI verb. Consider whether this is the natural landing spot for the third
  candidate slice considered today (`agentalloy why <symbol>`) or should stay
  narrower.
- **Multi-skill links.** If two promoted skills both name the same symbol, does
  the query return all of them, or does something rank/pick one? (AC 3 only
  requires *a* correct return, not this policy — design decides.)

---

*Next step per the SDD spec phase: present this spec, get explicit approval, then
`agentalloy approve spec` to seed the design work-item.*
