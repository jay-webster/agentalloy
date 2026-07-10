from pathlib import Path

import pytest
from automation.store import CandidateStore

from automation import cli


@pytest.fixture(autouse=True)
def _isolated_db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)


ADD_ARGS = [
    "ingest",
    "add",
    "--message-id",
    "msg-1",
    "--thread-id",
    "thread-1",
    "--source",
    "sender@example.com",
    "--subject",
    "An AI thing",
    "--received-at",
    "2026-07-10T09:00:00Z",
    "--snippet",
    "Something interesting.",
    "--ingested-at",
    "2026-07-10T10:00:00Z",
]


def test_add_then_add_again_is_idempotent(capsys: pytest.CaptureFixture[str]) -> None:
    first_exit = cli.main(ADD_ARGS)
    second_exit = cli.main(ADD_ARGS)

    assert first_exit == 0
    assert second_exit == 0
    store = CandidateStore()
    assert len(store.list()) == 1
    store.close()

    output = capsys.readouterr().out
    assert "already present" in output


def test_list_filters_by_status(capsys: pytest.CaptureFixture[str]) -> None:
    cli.main(ADD_ARGS)
    capsys.readouterr()

    exit_code = cli.main(["ingest", "list", "--status", "new"])

    assert exit_code == 0
    output = capsys.readouterr().out
    assert "msg-1" in output


def test_mark_missing_message_id_reports_not_found_and_exits_nonzero(
    capsys: pytest.CaptureFixture[str],
) -> None:
    exit_code = cli.main(["ingest", "mark", "does-not-exist", "accepted"])

    assert exit_code == 1
    err = capsys.readouterr().err
    assert "does-not-exist" in err
