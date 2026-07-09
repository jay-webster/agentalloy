"""symbol-linked-rationale, task 01: link_symbol / rationale_for_symbol."""

from __future__ import annotations

import pytest

from agentalloy.reads.rationale_links import link_symbol, rationale_for_symbol
from agentalloy.storage.skill_store import open_skill_store


@pytest.fixture
def store(tmp_path):
    ss = open_skill_store(str(tmp_path / "agentalloy.duck"))
    yield ss
    ss.close()


def _seed_skill(store, *, skill_id: str, rationale: str, deprecated: bool = False) -> None:
    version_id = f"{skill_id}-v1"
    store.execute(
        "INSERT INTO skills (skill_id, canonical_name, skill_class, category, "
        "deprecated, current_version_id) VALUES (?,?,?,?,?,?)",
        [skill_id, skill_id, "domain", "engineering", deprecated, version_id],
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


def test_link_then_query_round_trips(store):
    # T1.1
    _seed_skill(store, skill_id="skill-x", rationale="because the API rate-limits at 10 req/s")
    link_symbol(store, repo_slug="repo-a", qualified_name="pkg.foo", skill_id="skill-x")
    hits = rationale_for_symbol(store, repo_slug="repo-a", qualified_name="pkg.foo")
    assert len(hits) == 1
    assert hits[0].skill_id == "skill-x"
    assert hits[0].rationale == "because the API rate-limits at 10 req/s"


def test_unlinked_query_returns_empty_list(store):
    # T1.2
    assert rationale_for_symbol(store, repo_slug="repo-a", qualified_name="pkg.nope") == []


def test_links_are_scoped_per_repo(store):
    # T1.3 — same FQN, two different repos, must not cross-surface.
    _seed_skill(store, skill_id="skill-x", rationale="repo a's reason")
    _seed_skill(store, skill_id="skill-y", rationale="repo b's reason")
    link_symbol(store, repo_slug="repo-a", qualified_name="pkg.foo", skill_id="skill-x")
    link_symbol(store, repo_slug="repo-b", qualified_name="pkg.foo", skill_id="skill-y")

    a_hits = rationale_for_symbol(store, repo_slug="repo-a", qualified_name="pkg.foo")
    b_hits = rationale_for_symbol(store, repo_slug="repo-b", qualified_name="pkg.foo")
    assert [h.skill_id for h in a_hits] == ["skill-x"]
    assert [h.skill_id for h in b_hits] == ["skill-y"]


def test_multiple_skills_linked_to_one_symbol_all_returned(store):
    # T1.4
    _seed_skill(store, skill_id="skill-x", rationale="first reason")
    _seed_skill(store, skill_id="skill-y", rationale="second reason")
    link_symbol(store, repo_slug="repo-a", qualified_name="pkg.foo", skill_id="skill-x")
    link_symbol(store, repo_slug="repo-a", qualified_name="pkg.foo", skill_id="skill-y")

    hits = rationale_for_symbol(store, repo_slug="repo-a", qualified_name="pkg.foo")
    assert {h.skill_id for h in hits} == {"skill-x", "skill-y"}


def test_relinking_same_triple_is_idempotent(store):
    _seed_skill(store, skill_id="skill-x", rationale="reason")
    link_symbol(store, repo_slug="repo-a", qualified_name="pkg.foo", skill_id="skill-x")
    link_symbol(store, repo_slug="repo-a", qualified_name="pkg.foo", skill_id="skill-x")  # no-op
    hits = rationale_for_symbol(store, repo_slug="repo-a", qualified_name="pkg.foo")
    assert len(hits) == 1


def test_deprecated_skill_not_returned(store):
    _seed_skill(store, skill_id="skill-x", rationale="reason", deprecated=True)
    link_symbol(store, repo_slug="repo-a", qualified_name="pkg.foo", skill_id="skill-x")
    assert rationale_for_symbol(store, repo_slug="repo-a", qualified_name="pkg.foo") == []


def test_delete_skill_cleans_up_links(store):
    # T1.6
    _seed_skill(store, skill_id="skill-x", rationale="reason")
    link_symbol(store, repo_slug="repo-a", qualified_name="pkg.foo", skill_id="skill-x")
    assert rationale_for_symbol(store, repo_slug="repo-a", qualified_name="pkg.foo") != []

    store.delete_skill("skill-x")
    assert rationale_for_symbol(store, repo_slug="repo-a", qualified_name="pkg.foo") == []
    assert store.scalar("SELECT count(*) FROM symbol_rationale_links") == 0
