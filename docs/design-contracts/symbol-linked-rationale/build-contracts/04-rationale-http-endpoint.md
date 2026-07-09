---
phase: build
task_slug: 04-rationale-http-endpoint
route: full
# domain_tags: 1-2 tags, ONE dominant tech surface — never every surface.
# Build retrieval is ~4 skills per contract; a 7-tag basket starves most
# surfaces (important fragments truncate, scores muddy). Keep it narrow.
domain_tags:
  - fastapi
scope:
  touches:
    - "src/agentalloy/code_index/api/symbols_router.py"
  avoids:
    - "src/agentalloy/code_index/retrieval/**"
    - "src/agentalloy/retrieval/**"
success_criteria:
  - "GET /symbols/{fqn}/rationale returns linked rationale text for a linked symbol"
  - "the same endpoint returns an empty result (200, not 404/500) for an unlinked symbol"
  - "the existing GET /symbols/{fqn} endpoint's behavior and response shape are byte-for-byte unchanged"
related_contracts:
  - ".agentalloy/contracts/build/01-rationale-links-store.md"
created_at: 2026-07-09T21:02:26Z
---

# 04-rationale-http-endpoint

## Task

Add a new route to `src/agentalloy/code_index/api/symbols_router.py`:
`GET /symbols/{fqn:path}/rationale`, matching the file's existing three-route
shape (`require_indexed_repo(state, repo)` first, `repo` as a required `Query`
param, same docstring convention). **Register it before the bare
`GET /symbols/{fqn:path}` route** — the file's own docstring explains why
(`{fqn:path}` is greedy and starlette matches route order, which is exactly
why `/callers` and `/callees` are already registered first; this new route
joins that same group, in whatever order is simplest, all three ahead of the
bare route).

Unlike `/callers`/`/callees`/the bare route (which all call into
`h.graph` via `with_handles`), this handler's data lives in the **skill
corpus**, not the code graph — open the skill store read-only
(`open_skills(get_settings(), read_only=True)`, matching the existing
read-only-consumer convention) and call task 01's `rationale_for_symbol(store,
repo_slug=repo, qualified_name=fqn)`. Add a minimal response model
(`RationaleHitView` or similar, sibling to the existing `CallSiteView`/
`SymbolView` in `code_index/api/models.py`) rather than returning raw dicts,
matching this router's existing typed-response convention. Return `[]` for no
matches — 200, not 404 (a symbol having no linked rationale is not an error,
unlike the bare route's "no such symbol" 404, which is about the symbol itself
not existing in the graph at all — a different failure mode this route does
not need to replicate, since an unlinked-but-real symbol is a normal case).

## Test cases

From `docs/design/symbol-linked-rationale/test-plan.md`, Task 4 section:
T4.1 (AC3, a linked symbol's rationale comes back over HTTP), T4.2 (AC4, an
unlinked symbol returns `[]` with a 200, not an error status), T4.3 (AC8, the
existing `GET /symbols/{fqn}` test fixtures pass identically — a regression
guard proving this route is additive, not a rewrite).

## Plan

Approach + full task order live in `docs/design/symbol-linked-rationale/`
(`approach.md` §3, `tasks.md` task 4). Depends only on
`01-rationale-links-store`; independent of `02`/`03`.
