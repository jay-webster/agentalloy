"""retrieval.hybrid — dense ranking, pagerank fusion, RRF/BM25 merge, rewrite."""

from __future__ import annotations

from collections.abc import Iterator

import pytest

from agentalloy.code_index.api.state import CodeIndexState
from agentalloy.code_index.retrieval import hybrid
from agentalloy.code_index.retrieval.hybrid import (
    finalize_query_text,
    lexical_search,
    rewrite_query,
    semantic_search,
)
from agentalloy.code_index.store import open_jobs
from agentalloy.config import Settings

from .conftest import (
    FixedEmbedClient,
    axis_vec,
    make_symbol,
    mix_vec,
    seed_index,
    seed_rationale_link,
    vector_row,
)

SLUG = "repo"


@pytest.fixture
def state(settings: Settings) -> Iterator[CodeIndexState]:
    st = CodeIndexState(
        settings=settings, embed_client=FixedEmbedClient(axis_vec(0)), jobs=open_jobs(settings)
    )
    yield st
    st.jobs.close()


async def test_dense_ranking_respected(state: CodeIndexState) -> None:
    """No pagerank, no FTS index: results follow cosine order."""
    seed_index(
        state.settings,
        SLUG,
        symbols=[
            make_symbol("m.exact", docstring="The exact one."),
            make_symbol("m.partial"),
            make_symbol("m.orthogonal"),
        ],
        vectors=[
            vector_row("m.exact", axis_vec(0)),  # cosine 1.0
            vector_row("m.partial", axis_vec(0, 1)),  # cosine ~0.707
            vector_row("m.orthogonal", axis_vec(1)),  # cosine 0.0
        ],
    )
    results = await semantic_search(state, SLUG, "anything", k=10)
    assert [r.qualified_name for r in results] == ["m.exact", "m.partial", "m.orthogonal"]
    assert results[0].kind == "Function"
    assert results[0].file_path == "m/exact.py"
    assert results[0].snippet == "The exact one."
    assert results[0].score > results[1].score > results[2].score

    # k bound.
    assert len(await semantic_search(state, SLUG, "anything", k=2)) == 2


async def test_pagerank_fusion_reorders(state: CodeIndexState) -> None:
    """A low-cosine / high-pagerank symbol overtakes higher-cosine ones."""
    symbols = [make_symbol(qn) for qn in ("m.a", "m.b", "m.c")]
    vectors = [
        vector_row("m.a", axis_vec(0)),  # cosine 1.0
        vector_row("m.b", mix_vec(0, 1, 0.8, 0.6)),  # cosine 0.8
        vector_row("m.c", mix_vec(0, 1, 0.6, 0.8)),  # cosine 0.6
    ]
    # Without centrality the order is a, b, c.
    seed_index(state.settings, SLUG, symbols=symbols, vectors=vectors)
    baseline = await semantic_search(state, SLUG, "anything", k=3)
    assert [r.qualified_name for r in baseline] == ["m.a", "m.b", "m.c"]

    # 0.7*0.6 + 0.3*1.0 = 0.72 for m.c vs 0.7 for m.a vs 0.56 for m.b.
    seed_index(
        state.settings, "boosted", symbols=symbols, vectors=vectors,
        centrality={"m.a": 0.0, "m.b": 0.0, "m.c": 0.9},
    )  # fmt: skip
    boosted = await semantic_search(state, "boosted", "anything", k=3)
    assert [r.qualified_name for r in boosted] == ["m.c", "m.a", "m.b"]


async def test_rrf_merges_bm25_only_hit(
    state: CodeIndexState, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A hit outside the dense candidate pool enters via the BM25 leg."""
    monkeypatch.setattr(hybrid, "_FETCH_K", 2)
    seed_index(
        state.settings,
        SLUG,
        symbols=[make_symbol(qn) for qn in ("m.a", "m.b", "m.lexical")],
        vectors=[
            vector_row("m.a", axis_vec(0)),
            vector_row("m.b", axis_vec(0, 1)),
            # Orthogonal to the query — never in the dense top-2 — but the
            # only BM25 match for "zanzibar".
            vector_row("m.lexical", axis_vec(5), text="def lexical(): return 'zanzibar'"),
        ],
        fts=True,
    )
    results = await semantic_search(state, SLUG, "zanzibar", k=10)
    names = [r.qualified_name for r in results]
    assert "m.lexical" in names
    # RRF: dense [a, b] + bm25 [lexical] → a and lexical tie at 1/61, b at 1/62.
    assert names == ["m.a", "m.lexical", "m.b"]


async def test_lexical_search_hydrates_from_graph(state: CodeIndexState) -> None:
    seed_index(
        state.settings,
        SLUG,
        symbols=[make_symbol("m.frob", docstring="Frobnicates widgets.")],
        vectors=[vector_row("m.frob", axis_vec(0), text="def frobnicate(widget): pass")],
        fts=True,
    )
    results = await lexical_search(state, SLUG, "frobnicate", k=5)
    assert [r.qualified_name for r in results] == ["m.frob"]
    assert results[0].snippet == "Frobnicates widgets."
    assert results[0].score > 0.0

    # No FTS match — empty, not an error.
    assert await lexical_search(state, SLUG, "nomatchtoken", k=5) == []


async def test_semantic_search_surfaces_linked_rationale(state: CodeIndexState) -> None:
    # T#1 (AC1)
    seed_index(
        state.settings,
        SLUG,
        symbols=[make_symbol("m.exact", docstring="The exact one.")],
        vectors=[vector_row("m.exact", axis_vec(0))],
    )
    seed_rationale_link(
        state.settings.duckdb_path,
        repo_slug=SLUG,
        qualified_name="m.exact",
        skill_id="skill-x",
        rationale="because it rate-limits",
    )
    results = await semantic_search(state, SLUG, "anything", k=10)
    assert results[0].qualified_name == "m.exact"
    assert [hit.rationale for hit in results[0].rationale] == ["because it rate-limits"]


async def test_lexical_search_surfaces_linked_rationale(state: CodeIndexState) -> None:
    # T#2 (AC1)
    seed_index(
        state.settings,
        SLUG,
        symbols=[make_symbol("m.frob", docstring="Frobnicates widgets.")],
        vectors=[vector_row("m.frob", axis_vec(0), text="def frobnicate(widget): pass")],
        fts=True,
    )
    seed_rationale_link(
        state.settings.duckdb_path,
        repo_slug=SLUG,
        qualified_name="m.frob",
        skill_id="skill-y",
        rationale="handles the widget edge case",
    )
    results = await lexical_search(state, SLUG, "frobnicate", k=5)
    assert [hit.rationale for hit in results[0].rationale] == ["handles the widget edge case"]


async def test_unlinked_symbol_rationale_is_empty(state: CodeIndexState) -> None:
    # T#4 (AC3) — the common case: no link at all, not an error.
    seed_index(
        state.settings,
        SLUG,
        symbols=[make_symbol("m.exact", docstring="The exact one.")],
        vectors=[vector_row("m.exact", axis_vec(0))],
    )
    results = await semantic_search(state, SLUG, "anything", k=10)
    assert results[0].rationale == []
    assert results[0].file_path == "m/exact.py"
    assert results[0].snippet == "The exact one."


async def test_rationale_scoped_to_repo(state: CodeIndexState) -> None:
    # T#5 (AC5) — a link under a different repo_slug doesn't leak.
    seed_index(
        state.settings,
        SLUG,
        symbols=[make_symbol("m.exact", docstring="The exact one.")],
        vectors=[vector_row("m.exact", axis_vec(0))],
    )
    seed_rationale_link(
        state.settings.duckdb_path,
        repo_slug="other-repo",
        qualified_name="m.exact",
        skill_id="skill-z",
        rationale="scoped to another repo",
    )
    results = await semantic_search(state, SLUG, "anything", k=10)
    assert results[0].rationale == []


async def test_corpus_unreachable_degrades_to_empty_rationale(
    state: CodeIndexState, monkeypatch: pytest.MonkeyPatch
) -> None:
    # T#6 (AC6) — a corpus-open failure must not raise out of the request.
    monkeypatch.setattr(state.settings, "duckdb_path", "/nonexistent/dir/agentalloy.duck")
    seed_index(
        state.settings,
        SLUG,
        symbols=[make_symbol("m.exact", docstring="The exact one.")],
        vectors=[vector_row("m.exact", axis_vec(0))],
    )
    results = await semantic_search(state, SLUG, "anything", k=10)
    assert results[0].qualified_name == "m.exact"
    assert results[0].rationale == []


async def test_rationale_query_failure_degrades_to_empty_rationale(
    state: CodeIndexState, monkeypatch: pytest.MonkeyPatch
) -> None:
    # A query-time exception (not just a corpus-open failure) must not raise.
    from agentalloy.reads import rationale_links

    def _boom(*args: object, **kwargs: object) -> list[object]:
        raise RuntimeError("simulated query failure")

    monkeypatch.setattr(rationale_links, "rationale_for_symbol", _boom)
    seed_index(
        state.settings,
        SLUG,
        symbols=[make_symbol("m.exact", docstring="The exact one.")],
        vectors=[vector_row("m.exact", axis_vec(0))],
    )
    results = await semantic_search(state, SLUG, "anything", k=10)
    assert results[0].qualified_name == "m.exact"
    assert results[0].rationale == []


def test_rewrite_query_essence() -> None:
    # Long descriptive query: stop-words stripped.
    assert rewrite_query("how does the error envelope construction work") == (
        "error envelope construction work"
    )
    # Short queries pass through.
    assert rewrite_query("error envelope") == "error envelope"
    # Symbol-like tokens pass through.
    assert rewrite_query("where is pkg.util.helper defined exactly") == (
        "where is pkg.util.helper defined exactly"
    )
    # Over-strip guard: all-filler queries pass through.
    assert rewrite_query("how does it do that") == "how does it do that"


def test_finalize_query_text_prefix_and_cap() -> None:
    out = finalize_query_text("x" * 10_000)
    assert out.startswith("search_query: ")
    assert len(out) <= hybrid.MAX_EMBED_TEXT_CHARS
