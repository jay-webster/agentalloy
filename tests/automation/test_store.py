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


def test_reopening_store_does_not_raise_duplicate_column(tmp_path: Path) -> None:
    db_path = tmp_path / "candidates.db"
    CandidateStore(db_path=db_path).close()
    CandidateStore(db_path=db_path).close()


def test_migration_preserves_existing_row_data(tmp_path: Path) -> None:
    db_path = tmp_path / "candidates.db"
    first = CandidateStore(db_path=db_path)
    first.add(_candidate())
    first.close()

    reopened = CandidateStore(db_path=db_path)
    [row] = reopened.list()

    assert row.message_id == "msg-1"
    assert row.subject == "An AI thing"
    assert row.verdict is None
    assert row.rationale is None
    assert row.evaluated_at is None


def test_evaluate_sets_verdict_rationale_status_and_timestamp(
    store: CandidateStore,
) -> None:
    store.add(_candidate())

    updated = store.evaluate("msg-1", "accept", "good fit")

    assert updated is True
    [row] = store.list()
    assert row.status == "evaluated"
    assert row.verdict == "accept"
    assert row.rationale == "good fit"
    assert row.evaluated_at is not None


def test_reevaluating_overwrites_not_duplicates(store: CandidateStore) -> None:
    store.add(_candidate())
    store.evaluate("msg-1", "accept", "first pass")

    store.evaluate("msg-1", "reject", "changed my mind")

    assert len(store.list()) == 1
    [row] = store.list()
    assert row.verdict == "reject"
    assert row.rationale == "changed my mind"


def test_evaluate_missing_message_id_returns_false(store: CandidateStore) -> None:
    updated = store.evaluate("does-not-exist", "accept", "x")

    assert updated is False


def test_evaluate_invalid_verdict_raises_before_any_write(store: CandidateStore) -> None:
    store.add(_candidate())

    with pytest.raises(ValueError, match="maybe"):
        store.evaluate("msg-1", "maybe", "x")

    [row] = store.list()
    assert row.status == "new"
    assert row.verdict is None
