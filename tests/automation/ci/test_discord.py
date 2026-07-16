import json

import pytest

from automation.ci import discord


def test_chunk_message_short_message_returns_single_chunk_unchanged() -> None:
    message = "line1\nline2\nline3"

    chunks = discord.chunk_message(message, limit=2000)

    assert chunks == [message]


def test_chunk_message_splits_long_message_and_stays_under_limit() -> None:
    lines = [f"- #{i} some PR title padded out to be realistically long — url" for i in range(200)]
    message = "\n".join(lines)

    chunks = discord.chunk_message(message, limit=2000)

    assert len(chunks) > 1
    assert all(len(chunk) <= 2000 for chunk in chunks)


def test_chunk_message_never_breaks_a_line_mid_entry() -> None:
    lines = [f"- #{i} some PR title padded out to be realistically long — url" for i in range(200)]
    message = "\n".join(lines)

    chunks = discord.chunk_message(message, limit=2000)

    reconstructed = "\n".join(chunks)
    assert reconstructed == message


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
        captured["headers"] = {k.lower(): v for k, v in req.headers.items()}
        return _FakeResponse()

    monkeypatch.setattr(discord.urllib.request, "urlopen", _fake_urlopen)

    discord.post_to_discord("hello digest", "https://discord.example/webhook")

    assert captured["url"] == "https://discord.example/webhook"
    assert captured["body"] == {"content": "hello digest"}
    assert captured["headers"].get("user-agent", "").startswith("Python-urllib") is False
