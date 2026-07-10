from pathlib import Path

import pytest
from automation.store import Candidate, CandidateStore


@pytest.fixture
def store(tmp_path: Path) -> CandidateStore:
    return CandidateStore(db_path=tmp_path / "candidates.db")


def _candidate(message_id: str = "msg-1", status: str = "new") -> Candidate:
    return Candidate(
        message_id=message_id,
        thread_id="thread-1",
        source="sender@example.com",
        subject="An AI thing",
        received_at="2026-07-10T09:00:00Z",
        snippet="Something interesting happened.",
        ingested_at="2026-07-10T10:00:00Z",
        status=status,
    )


def test_add_is_idempotent_by_message_id(store: CandidateStore) -> None:
    first = store.add(_candidate())
    second = store.add(_candidate())

    assert first is True
    assert second is False
    assert len(store.list()) == 1


def test_new_candidates_default_to_status_new(store: CandidateStore) -> None:
    store.add(_candidate())

    [row] = store.list()
    assert row.status == "new"


def test_list_filters_by_status(store: CandidateStore) -> None:
    store.add(_candidate("msg-new", status="new"))
    store.add(_candidate("msg-evaluated", status="evaluated"))
    store.add(_candidate("msg-accepted", status="accepted"))

    new_only = store.list(status="new")

    assert [c.message_id for c in new_only] == ["msg-new"]


def test_mark_updates_existing_candidate(store: CandidateStore) -> None:
    store.add(_candidate())

    updated = store.mark("msg-1", "accepted")

    assert updated is True
    [row] = store.list(status="accepted")
    assert row.message_id == "msg-1"


def test_mark_missing_message_id_returns_false_not_an_exception(
    store: CandidateStore,
) -> None:
    updated = store.mark("does-not-exist", "accepted")

    assert updated is False
