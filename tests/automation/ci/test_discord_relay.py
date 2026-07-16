import pytest

from automation.ci import discord_relay


def test_main_posts_report_from_env_to_discord(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("REPORT", "PR Digest -- since 2026-07-11T00:00:00Z\n\nOpened (1):\n- #1 foo")
    monkeypatch.setenv("DISCORD_WEBHOOK_URL", "https://discord.example/webhook")
    posted = []
    monkeypatch.setattr(
        discord_relay, "post_to_discord", lambda message, webhook_url: posted.append(message)
    )

    exit_code = discord_relay.main()

    assert exit_code == 0
    assert len(posted) == 1
    assert posted[0] == "PR Digest -- since 2026-07-11T00:00:00Z\n\nOpened (1):\n- #1 foo"


def test_main_chunks_long_report_into_multiple_posts(monkeypatch: pytest.MonkeyPatch) -> None:
    lines = [f"- #{i} some realistically long PR title padded out further — url" for i in range(60)]
    report = "\n".join(lines)
    monkeypatch.setenv("REPORT", report)
    monkeypatch.setenv("DISCORD_WEBHOOK_URL", "https://discord.example/webhook")
    posted = []
    monkeypatch.setattr(
        discord_relay, "post_to_discord", lambda message, webhook_url: posted.append(message)
    )

    exit_code = discord_relay.main()

    assert exit_code == 0
    assert len(posted) > 1


def test_main_empty_webhook_url_skips_gracefully(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("REPORT", "some report")
    monkeypatch.setenv("DISCORD_WEBHOOK_URL", "")
    called = False

    def _fail_if_called(message: str, webhook_url: str) -> None:
        nonlocal called
        called = True

    monkeypatch.setattr(discord_relay, "post_to_discord", _fail_if_called)

    exit_code = discord_relay.main()

    assert exit_code == 0
    assert called is False
    assert "skipping" in capsys.readouterr().out.lower()


def test_main_missing_report_env_returns_nonzero_with_diagnostic(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.delenv("REPORT", raising=False)
    monkeypatch.delenv("DISCORD_WEBHOOK_URL", raising=False)

    exit_code = discord_relay.main()
    stderr = capsys.readouterr().err

    assert exit_code != 0
    assert "REPORT" in stderr
