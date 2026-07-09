"""GET /code/symbols/{fqn}/rationale — symbol-linked-rationale, task 04.

The data lives in the skill corpus (agentalloy.duck), not the code graph — a
different DB from the rest of this router's routes. The `settings` fixture in
conftest.py only isolates `code_index_data_dir`; these tests additionally
isolate `duckdb_path` so the skill-store half doesn't touch the real machine
corpus.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from agentalloy.app import create_app
from agentalloy.code_index.api.state import CodeIndexState, get_code_index_state
from agentalloy.code_index.store import open_jobs
from agentalloy.config import Settings
from agentalloy.reads.rationale_links import link_symbol
from agentalloy.storage.skill_store import open_skill_store

from .conftest import FixedEmbedClient, axis_vec, make_symbol, seed_index

SLUG = "demo"


@pytest.fixture
def isolated_settings(tmp_path) -> Settings:
    return Settings(
        code_index_data_dir=str(tmp_path / "code-index-data"),
        duckdb_path=str(tmp_path / "agentalloy.duck"),
    )


def _seed_promoted_skill(duckdb_path: str, *, skill_id: str, rationale: str) -> None:
    store = open_skill_store(duckdb_path)
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
    link_symbol(store, repo_slug=SLUG, qualified_name="pkg.util.helper", skill_id=skill_id)
    store.close()


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch, isolated_settings: Settings) -> Iterator[TestClient]:
    monkeypatch.setenv("CODE_INDEX_ENABLED", "1")
    seed_index(
        isolated_settings,
        SLUG,
        symbols=[make_symbol("pkg.util.helper", file_path="pkg/util.py")],
        edges=[],
    )
    state = CodeIndexState(
        settings=isolated_settings,
        embed_client=FixedEmbedClient(axis_vec(0)),
        jobs=open_jobs(isolated_settings),
    )
    state.jobs.upsert_repo(
        slug=SLUG, repo_path="/repo/demo", data_dir=isolated_settings.code_index_data_dir
    )
    app = create_app(use_default_lifespan=False)
    app.dependency_overrides[get_code_index_state] = lambda: state
    with TestClient(app) as c:
        yield c
    state.jobs.close()


def test_linked_symbol_returns_rationale(client: TestClient, isolated_settings: Settings) -> None:
    # T4.1 (AC3)
    _seed_promoted_skill(
        isolated_settings.duckdb_path, skill_id="skill-x", rationale="because it rate-limits"
    )
    resp = client.get("/code/symbols/pkg.util.helper/rationale", params={"repo": SLUG})
    assert resp.status_code == 200
    body = resp.json()
    assert body == [{"skill_id": "skill-x", "rationale": "because it rate-limits"}]


def test_unlinked_symbol_returns_empty_200(client: TestClient) -> None:
    # T4.2 (AC4) — no link at all is a normal case, not an error.
    resp = client.get("/code/symbols/pkg.util.helper/rationale", params={"repo": SLUG})
    assert resp.status_code == 200
    assert resp.json() == []


def test_unindexed_repo_still_404s(client: TestClient) -> None:
    resp = client.get("/code/symbols/pkg.util.helper/rationale", params={"repo": "ghost"})
    assert resp.status_code == 404
    assert "not indexed" in resp.json()["detail"]


def test_existing_bare_symbol_endpoint_unaffected(client: TestClient) -> None:
    # T4.3 (AC8) — the pre-existing GET /symbols/{fqn} route is untouched.
    resp = client.get("/code/symbols/pkg.util.helper", params={"repo": SLUG})
    assert resp.status_code == 200
    body = resp.json()
    assert body["qualified_name"] == "pkg.util.helper"
    assert body["file_path"] == "pkg/util.py"
