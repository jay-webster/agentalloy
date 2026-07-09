---
phase: build
task_slug: 03-promote-symbol-wiring
route: full
# domain_tags: 1-2 tags, ONE dominant tech surface — never every surface.
# Build retrieval is ~4 skills per contract; a 7-tag basket starves most
# surfaces (important fragments truncate, scores muddy). Keep it narrow.
domain_tags:
  - python
scope:
  touches:
    - "src/agentalloy/install/subcommands/lessons.py"
  avoids:
    - "src/agentalloy/retrieval/**"
    - "src/agentalloy/code_index/retrieval/**"
    - "src/agentalloy/api/proxy_signal.py"
    - "src/agentalloy/code_index/engine/**"
success_criteria:
  - "a lesson naming a symbol that resolves in the repo's code index creates a link row after promotion"
  - "a lesson naming a symbol that does not resolve is reported as unresolved, never blocks promotion"
  - "no code index for the repo at all (extra not installed, or never indexed) degrades identically to unresolved -- promotion behaves exactly as with no Symbols: line"
  - "the repo_slug used for the link is code_index.slug.repo_slug(root), not a guessed value"
related_contracts:
  - ".agentalloy/contracts/build/01-rationale-links-store.md"
  - ".agentalloy/contracts/build/02-symbols-line-parser.md"
created_at: 2026-07-09T21:02:25Z
---

# 03-promote-symbol-wiring

## Task

In `src/agentalloy/install/subcommands/lessons.py`'s `promote_lesson`, after
the existing install step succeeds, add symbol linking: call task 02's
`_lesson_symbols` on the lesson text (`lesson_path.read_text(...)`, already
read earlier in the function for `generate_lesson_pack`). If it returns
symbols, resolve `repo_slug = code_index.slug.repo_slug(root)` (the same
helper `contracts.py`'s `code_index_query_params` already uses — do not derive
a slug independently). For each named symbol, attempt
`open_code_index(get_settings(), repo_slug, role="reader")` then
`handles.graph.symbol(name)` to check existence — wrap this whole resolution
attempt in a broad `try/except`: a missing optional dependency (code-index
extra not installed), a never-indexed repo (`graph.duck` doesn't exist yet —
the store's own docstring says reader role "requires the graph file to
already exist"), or any other failure must all degrade identically to "this
symbol is unresolved," never raise out of `promote_lesson`. For each symbol
that *does* resolve, call task 01's `link_symbol(store, repo_slug=...,
qualified_name=name, skill_id=gen["skill_id"])` against the already-open skill
corpus (open once, not once per symbol). Collect unresolved names into the
returned result dict under a new key, e.g. `"unresolved_symbols"` (empty list
when there were none or no `Symbols:` line at all — never absent from the
result shape, so callers don't need `.get()` with a default).

This must not change any existing return action (`"promoted"`,
`"duplicate_refused"`, `"dedup_probe_failed"`, `"lesson_not_found"`,
`"invalid_slug"` if task 03 lands after the earlier path-traversal fix) —
symbol linking is additive to the `"promoted"` result only, and a linking
failure (as opposed to an unresolved name) must never turn a successful
promotion into a failed one.

## Test cases

From `docs/design/symbol-linked-rationale/test-plan.md`, Task 3 section:
T3.1 (AC1, a resolving symbol produces a real link row, verified via task 01's
query function, not just "no error"), T3.2 (AC2, an unresolved name is
reported, not linked, promotion still succeeds), T3.3 (no code index
configured at all degrades every name to unresolved — patch the
`open_code_index` import boundary in the test rather than requiring a real
`tree_sitter` install, same pattern the existing Piece 3 guard test already
uses for this exact problem), T3.4 (AC6, the link's `repo_slug` column matches
`code_index.slug.repo_slug(root)`'s actual output for the fixture root), T3.5
(AC7, no `lm_client`/embed import anywhere in the diff).

## Plan

Approach + full task order live in `docs/design/symbol-linked-rationale/`
(`approach.md` §1 & §4, `tasks.md` task 3). Depends on `01-rationale-links-store`
and `02-symbols-line-parser`; `04-rationale-http-endpoint` is independent of
this one (both depend only on 01).
