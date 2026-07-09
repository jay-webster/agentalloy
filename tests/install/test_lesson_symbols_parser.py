"""symbol-linked-rationale, task 02: the ``Symbols:`` line parser in isolation.

Sibling to ``_lesson_tags`` but must NOT slugify — a qualified name's dots are
load-bearing, unlike a tag's.
"""

from __future__ import annotations

from agentalloy.install.lesson_pack import _lesson_symbols  # pyright: ignore[reportPrivateUsage]


def test_symbols_line_preserves_dots_not_slugified():
    # T2.1
    text = "Symbols: pkg.foo.Bar, pkg.baz\n\nsome other prose\n"
    assert _lesson_symbols(text) == ["pkg.foo.Bar", "pkg.baz"]


def test_no_symbols_line_yields_empty_list_no_fallback():
    # T2.2 — unlike tags, there is no derived-from-id fallback.
    text = "# A lesson with no Symbols: line\n\n## Approach\n\ndid the thing\n"
    assert _lesson_symbols(text) == []


def test_semicolon_separator_and_whitespace():
    # T2.3
    text = "Symbols:  a.b ; c.d  \n"
    assert _lesson_symbols(text) == ["a.b", "c.d"]


def test_markdown_emphasis_wrapper_matches_like_tags_does():
    # The emphasis wraps the word, not word+colon together — same shape _TAGS_RE uses.
    text = "**Symbols**: agentalloy.retrieval.domain.skill_granular_select\n"
    assert _lesson_symbols(text) == ["agentalloy.retrieval.domain.skill_granular_select"]


def test_duplicate_entries_deduped_order_preserving():
    text = "Symbols: a.b, c.d, a.b\n"
    assert _lesson_symbols(text) == ["a.b", "c.d"]


def test_case_insensitive_label():
    text = "symbols: pkg.Foo\n"
    assert _lesson_symbols(text) == ["pkg.Foo"]
