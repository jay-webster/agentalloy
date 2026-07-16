import json

import pytest

from automation.ci import pr_approved


def _pr(**overrides: object) -> dict:
    base = {
        "number": 42,
        "title": "Add retry logic",
        "url": "https://github.com/x/y/pull/42",
    }
    base.update(overrides)
    return base


def test_format_approval_notice_includes_number_title_reviewer_url() -> None:
    pr = _pr()
    review = {"user": {"login": "jay-webster"}, "state": "approved"}

    notice = pr_approved.format_approval_notice(pr, review)

    assert notice == "#42 Add retry logic approved by jay-webster — https://github.com/x/y/pull/42"


def test_format_approval_notice_degrades_gracefully_on_missing_reviewer() -> None:
    pr = _pr()
    review = {"state": "approved"}

    notice = pr_approved.format_approval_notice(pr, review)

    assert "#42 Add retry logic approved by someone" in notice


def test_main_posts_single_message_on_success(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PR_JSON", json.dumps(_pr()))
    monkeypatch.setenv("REVIEW_JSON", json.dumps({"user": {"login": "jay-webster"}}))
    monkeypatch.setenv("DISCORD_WEBHOOK_URL", "https://discord.example/webhook")
    posted = []
    monkeypatch.setattr(
        pr_approved, "post_to_discord", lambda message, webhook_url: posted.append(message)
    )

    exit_code = pr_approved.main()

    assert exit_code == 0
    assert len(posted) == 1
    assert (
        posted[0] == "#42 Add retry logic approved by jay-webster — https://github.com/x/y/pull/42"
    )


def test_main_empty_webhook_url_skips_gracefully(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("PR_JSON", json.dumps(_pr()))
    monkeypatch.setenv("REVIEW_JSON", json.dumps({"user": {"login": "jay-webster"}}))
    monkeypatch.setenv("DISCORD_WEBHOOK_URL", "")
    called = False

    def _fail_if_called(message: str, webhook_url: str) -> None:
        nonlocal called
        called = True

    monkeypatch.setattr(pr_approved, "post_to_discord", _fail_if_called)

    exit_code = pr_approved.main()

    assert exit_code == 0
    assert called is False
    assert "skipping" in capsys.readouterr().out.lower()


def test_main_missing_env_returns_nonzero_with_diagnostic(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.delenv("PR_JSON", raising=False)
    monkeypatch.delenv("REVIEW_JSON", raising=False)
    monkeypatch.delenv("DISCORD_WEBHOOK_URL", raising=False)

    exit_code = pr_approved.main()
    stderr = capsys.readouterr().err

    assert exit_code != 0
    assert "PR_JSON" in stderr
