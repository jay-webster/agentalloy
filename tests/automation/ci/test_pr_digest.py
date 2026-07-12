import io
import json

import pytest

from automation.ci import pr_digest


def _pr(**overrides: object) -> dict:
    base = {
        "number": 1,
        "title": "Some PR",
        "url": "https://github.com/x/y/pull/1",
        "createdAt": "2026-07-10T00:00:00Z",
        "mergedAt": None,
        "state": "OPEN",
        "mergedBy": None,
    }
    base.update(overrides)
    return base


def test_pr_created_in_window_appears_in_opened() -> None:
    pr = _pr(number=1, title="New feature", createdAt="2026-07-11T12:00:00Z", state="OPEN")

    digest = pr_digest.format_digest([pr], since="2026-07-11T00:00:00Z")

    assert "Opened (1)" in digest
    assert "#1 New feature" in digest


def test_pr_merged_in_window_appears_in_merged() -> None:
    pr = _pr(
        number=2,
        title="Fix bug",
        createdAt="2026-07-09T00:00:00Z",
        mergedAt="2026-07-11T12:00:00Z",
        state="MERGED",
    )

    digest = pr_digest.format_digest([pr], since="2026-07-11T00:00:00Z")

    assert "Merged (1)" in digest
    assert "#2 Fix bug" in digest


def test_currently_open_pr_appears_in_still_open_regardless_of_age() -> None:
    pr = _pr(number=3, title="Old PR", createdAt="2020-01-01T00:00:00Z", state="OPEN")

    digest = pr_digest.format_digest([pr], since="2026-07-11T00:00:00Z")

    assert "Still open (1)" in digest
    assert "#3 Old PR" in digest


def test_merged_pr_with_bot_merger_labeled_auto_merged() -> None:
    pr = _pr(
        number=4,
        mergedAt="2026-07-11T12:00:00Z",
        state="MERGED",
        mergedBy={"login": "github-actions[bot]", "is_bot": True},
    )

    digest = pr_digest.format_digest([pr], since="2026-07-11T00:00:00Z")

    assert "auto-merged" in digest


def test_merged_pr_with_human_merger_labeled_manually_merged() -> None:
    pr = _pr(
        number=5,
        mergedAt="2026-07-11T12:00:00Z",
        state="MERGED",
        mergedBy={"login": "jay-webster", "is_bot": False},
    )

    digest = pr_digest.format_digest([pr], since="2026-07-11T00:00:00Z")

    assert "manually merged" in digest


def test_merged_pr_with_missing_merger_degrades_to_bare_merged() -> None:
    pr = _pr(number=6, mergedAt="2026-07-11T12:00:00Z", state="MERGED", mergedBy=None)

    digest = pr_digest.format_digest([pr], since="2026-07-11T00:00:00Z")

    assert "#6" in digest
    assert "auto-merged" not in digest
    assert "manually merged" not in digest


def test_empty_window_produces_short_nothing_to_report_line() -> None:
    pr = _pr(
        number=7,
        createdAt="2020-01-01T00:00:00Z",
        mergedAt="2020-01-02T00:00:00Z",
        state="MERGED",
    )

    digest = pr_digest.format_digest([pr], since="2026-07-11T00:00:00Z")

    assert digest == "PR Digest — nothing to report since 2026-07-11T00:00:00Z."


def test_pr_outside_window_and_not_open_appears_in_no_bucket() -> None:
    pr = _pr(
        number=8,
        createdAt="2020-01-01T00:00:00Z",
        mergedAt="2020-01-02T00:00:00Z",
        state="CLOSED",
    )
    live_pr = _pr(number=9, createdAt="2026-07-11T12:00:00Z", state="OPEN")

    digest = pr_digest.format_digest([pr, live_pr], since="2026-07-11T00:00:00Z")

    assert "#8" not in digest


def test_post_to_discord_sends_content_field_to_webhook_url(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured = {}

    class _FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def read(self):
            return b""

    def _fake_urlopen(req, timeout=None):
        captured["url"] = req.full_url
        captured["body"] = json.loads(req.data)
        return _FakeResponse()

    monkeypatch.setattr(pr_digest.urllib.request, "urlopen", _fake_urlopen)

    pr_digest.post_to_discord("hello digest", "https://discord.example/webhook")

    assert captured["url"] == "https://discord.example/webhook"
    assert captured["body"] == {"content": "hello digest"}


def test_main_returns_zero_on_success(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SINCE", "2026-07-11T00:00:00Z")
    monkeypatch.setenv("DISCORD_WEBHOOK_URL", "https://discord.example/webhook")
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps([_pr(number=1, state="OPEN")])))
    monkeypatch.setattr(pr_digest, "post_to_discord", lambda message, webhook_url: None)

    exit_code = pr_digest.main()

    assert exit_code == 0


def test_main_missing_env_var_returns_nonzero_with_diagnostic(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.delenv("SINCE", raising=False)
    monkeypatch.delenv("DISCORD_WEBHOOK_URL", raising=False)
    monkeypatch.setattr("sys.stdin", io.StringIO("[]"))

    exit_code = pr_digest.main()
    stderr = capsys.readouterr().err

    assert exit_code != 0
    assert "SINCE" in stderr
