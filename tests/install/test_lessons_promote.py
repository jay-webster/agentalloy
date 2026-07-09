"""Task 04: ``lessons promote`` CLI — the pre-ingest dedup probe (AC 5).

AC 5: promoting a lesson whose fragments duplicate an existing corpus skill
(cosine >= 0.92) is refused BEFORE install (the near-duplicate is never written),
unless ``--allow-duplicates`` is passed. Verified with injected embed/store/install
seams so the logic is exercised without the real embed model or corpus.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from agentalloy.install.subcommands.lessons import (
    add_parser,
    probe_lesson_duplicates,
    promote_lesson,
)

LESSON = "# A lesson\n\n## Approach\n\nDo the thing that worked, carefully and in order, then confirm it.\n"


@dataclass
class _Hit:
    fragment_id: str
    skill_id: str
    distance: float


class _FakeStore:
    """A FragmentStore stub whose search returns a fixed hit list."""

    def __init__(self, hits: list[_Hit]):
        self._hits = hits
        self.closed = False

    def search_similar(
        self, query_vec: Any, *, k: int = 20, categories: Any = None, fragment_types: Any = None
    ) -> list[_Hit]:
        return list(self._hits)

    def close(self) -> None:
        self.closed = True


def _embed(_text: str) -> list[float]:
    return [0.1, 0.2, 0.3]


def _write_lesson(root: Path, slug: str, body: str = LESSON) -> None:
    p = root / "docs" / "solutions" / f"{slug}.md"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(body, encoding="utf-8")


# --- the probe in isolation ------------------------------------------------


def test_probe_flags_hard_hit():
    store = _FakeStore([_Hit("existing-f0", "existing-skill", distance=0.05)])  # sim 0.95 >= 0.92
    hits = probe_lesson_duplicates(
        ["frag a", "frag b"],
        embed=_embed,
        vector_store=store,
        hard_similarity=0.92,
        soft_similarity=0.80,
    )
    assert hits and hits[0].skill_id == "existing-skill"


def test_probe_ignores_soft_only():
    store = _FakeStore([_Hit("existing-f0", "existing-skill", distance=0.15)])  # sim 0.85 -> soft
    hits = probe_lesson_duplicates(
        ["frag a"], embed=_embed, vector_store=store, hard_similarity=0.92, soft_similarity=0.80
    )
    assert hits == []


# --- promote flow: refuse vs install ---------------------------------------


def test_ac5_hard_duplicate_refused_and_not_installed(tmp_path: Path):
    _write_lesson(tmp_path, "dup-lesson")
    installed: list[Path] = []

    def _install(pack_dir: Path, **_kw: Any) -> dict[str, Any]:
        installed.append(pack_dir)
        return {"ok": True}

    res = promote_lesson(
        "dup-lesson",
        root=tmp_path,
        embed=_embed,
        vector_store=_FakeStore([_Hit("x-f0", "existing-skill", distance=0.02)]),
        install=_install,
    )
    assert res["action"] == "duplicate_refused"
    assert res["duplicates"] == ["existing-skill"]
    assert installed == []  # the rail was never reached -> nothing written to the corpus


def test_ac5_allow_duplicates_installs(tmp_path: Path):
    _write_lesson(tmp_path, "dup-lesson")
    installed: list[Path] = []

    def _install(pack_dir: Path, **_kw: Any) -> dict[str, Any]:
        installed.append(pack_dir)
        return {"ok": True}

    res = promote_lesson(
        "dup-lesson",
        root=tmp_path,
        allow_duplicates=True,
        embed=_embed,
        vector_store=_FakeStore([_Hit("x-f0", "existing-skill", distance=0.02)]),
        install=_install,
    )
    assert res["action"] == "promoted"
    assert len(installed) == 1


def test_unique_lesson_installs(tmp_path: Path):
    _write_lesson(tmp_path, "fresh-lesson")
    installed: list[Path] = []

    def _install(pack_dir: Path, **_kw: Any) -> dict[str, Any]:
        installed.append(pack_dir)
        return {"ok": True}

    res = promote_lesson(
        "fresh-lesson",
        root=tmp_path,
        embed=_embed,
        vector_store=_FakeStore([]),  # nothing similar in the corpus
        install=_install,
    )
    assert res["action"] == "promoted"
    assert len(installed) == 1


def test_unknown_slug_reported(tmp_path: Path):
    res = promote_lesson(
        "does-not-exist",
        root=tmp_path,
        embed=_embed,
        vector_store=_FakeStore([]),
        install=lambda *a, **k: {},
    )
    assert res["action"] == "lesson_not_found"


def test_path_traversal_slug_rejected_before_any_read(tmp_path: Path):
    # `slug` is a CLI arg used directly to build the lesson-read path
    # (root/docs/solutions/<slug>.md) before generate_lesson_pack or the dedup
    # probe ever run. A secret file placed one level above docs/solutions/ must
    # never be reachable via `../` in the slug.
    secret = tmp_path / "secret.md"
    secret.write_text("do not leak this\n", encoding="utf-8")
    (tmp_path / "docs" / "solutions").mkdir(parents=True)

    for bad_slug in ("../secret", "../../etc/passwd", "foo/bar", "..", "/etc/passwd", "a" * 65):
        res = promote_lesson(
            bad_slug,
            root=tmp_path,
            embed=_embed,
            vector_store=_FakeStore([]),
            install=lambda *a, **k: {},
        )
        assert res["action"] == "invalid_slug", bad_slug
        assert "disallowed characters" in res["error"]


def test_no_corpus_skips_probe_and_installs(tmp_path: Path, monkeypatch):
    """When the fragment store cannot be opened (fresh install, no corpus), the
    probe is skipped — there is nothing to duplicate against — and install runs."""
    _write_lesson(tmp_path, "fresh-lesson")
    installed: list[Path] = []

    def _boom(*_a, **_k):
        raise RuntimeError("no corpus")

    monkeypatch.setattr("agentalloy.storage.open.open_fragments", _boom)
    res = promote_lesson(
        "fresh-lesson",
        root=tmp_path,
        embed=_embed,
        vector_store=None,  # None -> tries open_fragments (patched to fail) -> skip
        install=lambda pack_dir, **_k: installed.append(pack_dir) or {"ok": True},
    )
    assert res["action"] == "promoted"
    assert len(installed) == 1


def test_probe_failure_fails_closed(tmp_path: Path):
    """If the probe itself errors (e.g. embed server down), promotion is refused
    rather than installing unchecked — fail closed."""
    _write_lesson(tmp_path, "err-lesson")
    installed: list[Path] = []

    def _bad_embed(_text: str) -> list[float]:
        raise RuntimeError("embed server down")

    res = promote_lesson(
        "err-lesson",
        root=tmp_path,
        embed=_bad_embed,
        vector_store=_FakeStore([]),
        install=lambda pack_dir, **_k: installed.append(pack_dir) or {"ok": True},
    )
    assert res["action"] == "dedup_probe_failed"
    assert installed == []


# --- CLI registration ------------------------------------------------------


def test_promote_registered_and_parses():
    import argparse

    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="subcommand")
    add_parser(sub)
    args = parser.parse_args(["lessons", "promote", "my-slug", "--allow-duplicates"])
    assert args.slug == "my-slug"
    assert args.allow_duplicates is True
    assert callable(args.func)


# --- symbol-linked-rationale wiring (task 03) -------------------------------

LESSON_WITH_SYMBOLS = (
    "# A lesson\n\n"
    "Symbols: pkg.foo.Bar, pkg.baz\n\n"
    "## Approach\n\nDo the thing that worked, carefully and in order, then confirm it.\n"
)


def _fake_install(pack_dir: Any, **_kw: Any) -> dict[str, Any]:
    return {"action": "ingested", "dedup_exit_code": 0}


def _seed_promoted_skill(store: Any, *, skill_id: str, rationale: str = "the reason") -> None:
    """Mimic what a real install_local_pack run would have written for
    `skill_id` — _fake_install is a no-op stub, so these tests seed the
    minimal skills/skill_versions/fragments rows rationale_for_symbol's join
    needs, using the same `store` handle promote_lesson linked against."""
    version_id = f"{skill_id}-v1"
    store.execute(
        "INSERT INTO skills (skill_id, canonical_name, skill_class, category, "
        "deprecated, current_version_id) VALUES (?,?,?,?,?,?)",
        [skill_id, skill_id, "domain", "engineering", False, version_id],
    )
    store.execute(
        "INSERT INTO skill_versions (version_id, skill_id, version_number, status, raw_prose) "
        "VALUES (?,?,?,?,?)",
        [version_id, skill_id, 1, "active", rationale],
    )
    store.execute(
        "INSERT INTO fragments (fragment_id, version_id, fragment_type, sequence, content) "
        "VALUES (?,?,?,?,?)",
        [f"{skill_id}-f0", version_id, "rationale", 0, rationale],
    )


def test_resolving_symbols_create_link_rows(tmp_path: Path):
    # T3.1 (AC1) — a real link row exists afterward, verified via task 01's
    # own query function, not just "no error".
    from agentalloy.code_index.slug import repo_slug as real_repo_slug
    from agentalloy.reads.rationale_links import rationale_for_symbol
    from agentalloy.storage.skill_store import open_skill_store

    _write_lesson(tmp_path, "sym-lesson", body=LESSON_WITH_SYMBOLS)
    store = open_skill_store(str(tmp_path / "agentalloy.duck"))
    slug = real_repo_slug(tmp_path)

    res = promote_lesson(
        "sym-lesson",
        root=tmp_path,
        embed=_embed,
        vector_store=_FakeStore([]),
        install=_fake_install,
        symbol_resolver=lambda repo, name: True,  # everything resolves
        skill_store=store,
    )
    assert res["action"] == "promoted"
    assert res["unresolved_symbols"] == []
    _seed_promoted_skill(store, skill_id=res["skill_id"])

    for name in ("pkg.foo.Bar", "pkg.baz"):
        hits = rationale_for_symbol(store, repo_slug=slug, qualified_name=name)
        assert [h.skill_id for h in hits] == [res["skill_id"]]
    store.close()


def test_unresolvable_symbol_reported_not_linked_promotion_still_succeeds(tmp_path: Path):
    # T3.2 (AC2)
    from agentalloy.code_index.slug import repo_slug as real_repo_slug
    from agentalloy.reads.rationale_links import rationale_for_symbol
    from agentalloy.storage.skill_store import open_skill_store

    _write_lesson(tmp_path, "sym-lesson", body=LESSON_WITH_SYMBOLS)
    store = open_skill_store(str(tmp_path / "agentalloy.duck"))
    slug = real_repo_slug(tmp_path)

    def _resolver(repo: str, name: str) -> bool:
        return name == "pkg.foo.Bar"  # pkg.baz does not resolve

    res = promote_lesson(
        "sym-lesson",
        root=tmp_path,
        embed=_embed,
        vector_store=_FakeStore([]),
        install=_fake_install,
        symbol_resolver=_resolver,
        skill_store=store,
    )
    assert res["action"] == "promoted"
    assert res["unresolved_symbols"] == ["pkg.baz"]
    _seed_promoted_skill(store, skill_id=res["skill_id"])
    assert rationale_for_symbol(store, repo_slug=slug, qualified_name="pkg.baz") == []
    hits = rationale_for_symbol(store, repo_slug=slug, qualified_name="pkg.foo.Bar")
    assert [h.skill_id for h in hits] == [res["skill_id"]]
    store.close()


def test_no_code_index_degrades_every_symbol_to_unresolved(tmp_path: Path, monkeypatch):
    # T3.3 — patches the open_code_index import boundary rather than requiring
    # a real tree_sitter install, same pattern the existing Piece 3 guard test
    # already uses for this exact optional-dependency problem.
    def _boom(*_a: Any, **_k: Any) -> Any:
        raise ModuleNotFoundError("no module named 'tree_sitter'")

    monkeypatch.setattr("agentalloy.code_index.store.open.open_code_index", _boom)
    _write_lesson(tmp_path, "sym-lesson", body=LESSON_WITH_SYMBOLS)

    res = promote_lesson(
        "sym-lesson",
        root=tmp_path,
        embed=_embed,
        vector_store=_FakeStore([]),
        install=_fake_install,
        # no symbol_resolver override -> exercises the real _default_symbol_exists,
        # which must degrade to False via the patched open_code_index, never raise.
    )
    assert res["action"] == "promoted"
    assert res["unresolved_symbols"] == ["pkg.foo.Bar", "pkg.baz"]


def test_lesson_with_no_symbols_line_is_unaffected(tmp_path: Path):
    # Backward-compat guard: a plain lesson (no Symbols: line) behaves exactly
    # as before this feature — empty unresolved list, no resolver/store touched.
    _write_lesson(tmp_path, "plain-lesson")

    def _resolver_should_not_be_called(repo: str, name: str) -> bool:
        raise AssertionError("resolver must not be called when there is no Symbols: line")

    res = promote_lesson(
        "plain-lesson",
        root=tmp_path,
        embed=_embed,
        vector_store=_FakeStore([]),
        install=_fake_install,
        symbol_resolver=_resolver_should_not_be_called,
    )
    assert res["action"] == "promoted"
    assert res["unresolved_symbols"] == []


def test_link_repo_slug_matches_code_index_slug_helper(tmp_path: Path):
    # T3.4 (AC6) — the link's repo_slug is code_index.slug.repo_slug(root)'s
    # actual output, not a guessed/hardcoded value.
    from agentalloy.code_index.slug import repo_slug as real_repo_slug
    from agentalloy.reads.rationale_links import rationale_for_symbol
    from agentalloy.storage.skill_store import open_skill_store

    _write_lesson(tmp_path, "sym-lesson", body=LESSON_WITH_SYMBOLS)
    store = open_skill_store(str(tmp_path / "agentalloy.duck"))
    expected_slug = real_repo_slug(tmp_path)

    res = promote_lesson(
        "sym-lesson",
        root=tmp_path,
        embed=_embed,
        vector_store=_FakeStore([]),
        install=_fake_install,
        symbol_resolver=lambda repo, name: True,
        skill_store=store,
    )
    _seed_promoted_skill(store, skill_id=res["skill_id"])
    hits = rationale_for_symbol(store, repo_slug=expected_slug, qualified_name="pkg.foo.Bar")
    assert [h.skill_id for h in hits] == [res["skill_id"]]
    store.close()
