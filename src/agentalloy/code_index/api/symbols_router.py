"""Symbol-relation endpoints (``/code/symbols/*``).

``fqn`` is the path (``:path`` converter so dotted — and any future
slash-bearing — names round-trip); ``repo`` is a required query param. The
``/callers`` and ``/callees`` routes are registered BEFORE the bare symbol
route: starlette matches in order and the greedy ``{fqn:path}`` would
otherwise swallow the literal suffix segments.
"""

from __future__ import annotations

import asyncio

from fastapi import APIRouter, Depends, HTTPException, Query

from agentalloy.code_index.api.deps import require_indexed_repo, with_handles
from agentalloy.code_index.api.models import CallSiteView, RationaleHitView, SymbolView
from agentalloy.code_index.api.state import CodeIndexState, get_code_index_state

router = APIRouter()


@router.get(
    "/symbols/{fqn:path}/rationale",
    response_model=list[RationaleHitView],
    summary="Promoted skills linked to fqn (symbol-linked-rationale) — [] if none",
)
async def symbol_rationale(
    fqn: str,
    repo: str = Query(description="Indexed repo slug"),
    state: CodeIndexState = Depends(get_code_index_state),
) -> list[RationaleHitView]:
    # Registered before the bare /symbols/{fqn:path} route below, same reason
    # /callers and /callees are — the greedy {fqn:path} converter would
    # otherwise swallow this route's literal /rationale suffix.
    #
    # Unlike /callers, /callees, and the bare route, this handler's data lives
    # in the SKILL corpus (agentalloy.duck), not the code graph — it never
    # touches h.graph via with_handles. require_indexed_repo still applies: a
    # rationale query is only meaningful for a repo that's actually indexed.
    require_indexed_repo(state, repo)

    def _read() -> list[RationaleHitView]:
        from agentalloy.reads.rationale_links import rationale_for_symbol
        from agentalloy.storage.open import open_skills

        try:
            store = open_skills(state.settings, read_only=True)
        except Exception:
            # No skill corpus at all yet (e.g. nothing has ever been
            # promoted here) — "no link" is not an error (AC4).
            return []
        try:
            hits = rationale_for_symbol(store, repo_slug=repo, qualified_name=fqn)
        finally:
            store.close()
        return [RationaleHitView.from_hit(h) for h in hits]

    return await asyncio.to_thread(_read)


@router.get(
    "/symbols/{fqn:path}/callers",
    response_model=list[CallSiteView],
    summary="Symbols that call fqn (depth > 1 walks transitively)",
)
async def symbol_callers(
    fqn: str,
    repo: str = Query(description="Indexed repo slug"),
    depth: int = Query(default=1, ge=1, le=10),
    state: CodeIndexState = Depends(get_code_index_state),
) -> list[CallSiteView]:
    require_indexed_repo(state, repo)
    sites = await with_handles(
        state,
        repo,
        lambda h: (
            h.graph.callers(fqn) if depth == 1 else h.graph.transitive_callers(fqn, max_depth=depth)
        ),
    )
    return [CallSiteView.from_call_site(s) for s in sites]


@router.get(
    "/symbols/{fqn:path}/callees",
    response_model=list[CallSiteView],
    summary="Symbols fqn calls",
)
async def symbol_callees(
    fqn: str,
    repo: str = Query(description="Indexed repo slug"),
    state: CodeIndexState = Depends(get_code_index_state),
) -> list[CallSiteView]:
    require_indexed_repo(state, repo)
    sites = await with_handles(state, repo, lambda h: h.graph.callees(fqn))
    return [CallSiteView.from_call_site(s) for s in sites]


@router.get(
    "/symbols/{fqn:path}",
    response_model=SymbolView,
    summary="One symbol's full graph row",
)
async def symbol_detail(
    fqn: str,
    repo: str = Query(description="Indexed repo slug"),
    state: CodeIndexState = Depends(get_code_index_state),
) -> SymbolView:
    require_indexed_repo(state, repo)
    sym = await with_handles(state, repo, lambda h: h.graph.symbol(fqn))
    if sym is None:
        raise HTTPException(status_code=404, detail=f"no such symbol in {repo!r}: {fqn}")
    return SymbolView.from_symbol(sym)
