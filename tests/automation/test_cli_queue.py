"""Tests for the `ingest queue-verdict`/`queue-list`/`queue-clear` CLI subcommands."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from automation import cli, review_queue


@pytest.fixture(autouse=True)
def _isolated_cwd(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)


def test_queue_verdict_writes_one_line_and_exits_zero(
    capsys: pytest.CaptureFixture[str],
) -> None:
    exit_code = cli.main(
        [
            "ingest",
            "queue-verdict",
            "--message-id",
            "url-1",
            "--verdict",
            "reject",
            "--rationale",
            "no lens fires",
        ]
    )

    assert exit_code == 0
    rows = review_queue.list_pending()
    assert rows == [{"message_id": "url-1", "verdict": "reject", "rationale": "no lens fires"}]


def test_queue_verdict_invalid_verdict_exits_nonzero_and_writes_nothing(
    capsys: pytest.CaptureFixture[str],
) -> None:
    with pytest.raises(SystemExit) as exc_info:
        cli.main(
            [
                "ingest",
                "queue-verdict",
                "--message-id",
                "url-1",
                "--verdict",
                "bogus",
                "--rationale",
                "x",
            ]
        )

    assert exc_info.value.code != 0
    assert review_queue.list_pending() == []


def test_queue_list_empty_prints_nothing_pending(capsys: pytest.CaptureFixture[str]) -> None:
    exit_code = cli.main(["ingest", "queue-list"])

    assert exit_code == 0
    output = capsys.readouterr().out
    assert "nothing pending" in output


def test_queue_list_prints_pending_rows(capsys: pytest.CaptureFixture[str]) -> None:
    cli.main(
        [
            "ingest",
            "queue-verdict",
            "--message-id",
            "url-1",
            "--verdict",
            "accept",
            "--rationale",
            "matches feature fit",
        ]
    )
    capsys.readouterr()

    exit_code = cli.main(["ingest", "queue-list"])
    output = capsys.readouterr().out

    assert exit_code == 0
    assert "url-1" in output
    assert "accept" in output
    assert "matches feature fit" in output


def test_queue_clear_then_list_shows_nothing_pending(
    capsys: pytest.CaptureFixture[str],
) -> None:
    cli.main(
        [
            "ingest",
            "queue-verdict",
            "--message-id",
            "url-1",
            "--verdict",
            "accept",
            "--rationale",
            "x",
        ]
    )
    capsys.readouterr()

    clear_exit = cli.main(["ingest", "queue-clear"])
    capsys.readouterr()
    list_exit = cli.main(["ingest", "queue-list"])
    output = capsys.readouterr().out

    assert clear_exit == 0
    assert list_exit == 0
    assert "nothing pending" in output


def test_queue_handlers_have_no_drive_or_network_call_sites() -> None:
    cli_path = Path(__file__).resolve().parents[2] / "automation" / "cli.py"
    source = cli_path.read_text()
    match = re.search(r"def _cmd_queue_verdict.*?(?=\ndef _format_candidate)", source, re.DOTALL)
    assert match is not None
    handlers_source = match.group(0)

    forbidden_literals = ("googleapis", "requests", "httpx", "curl")
    for literal in forbidden_literals:
        assert literal not in handlers_source, f"unexpected {literal!r} in queue handlers"
    assert not re.search(r"google.*drive", handlers_source, re.IGNORECASE)
