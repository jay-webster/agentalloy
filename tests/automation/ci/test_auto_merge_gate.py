import io

import pytest

from automation.ci import auto_merge_gate


def test_all_allowlisted_paths_prints_low(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr("sys.stdin", io.StringIO("src/agentalloy/_packs/core/x.yaml\ndocs/y.md\n"))

    exit_code = auto_merge_gate.main()

    assert exit_code == 0
    assert capsys.readouterr().out.strip() == "low"


def test_one_disallowed_path_prints_high(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(
        "sys.stdin", io.StringIO("src/agentalloy/_packs/core/x.yaml\nautomation/store.py\n")
    )

    auto_merge_gate.main()

    assert capsys.readouterr().out.strip() == "high"


def test_all_disallowed_paths_prints_high(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr("sys.stdin", io.StringIO("src/agentalloy/retrieval/hybrid.py\n"))

    auto_merge_gate.main()

    assert capsys.readouterr().out.strip() == "high"


def test_empty_stdin_prints_high(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr("sys.stdin", io.StringIO(""))

    auto_merge_gate.main()

    assert capsys.readouterr().out.strip() == "high"


def test_trailing_blank_line_does_not_corrupt_classification(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr("sys.stdin", io.StringIO("docs/y.md\n\n"))

    auto_merge_gate.main()

    assert capsys.readouterr().out.strip() == "low"
