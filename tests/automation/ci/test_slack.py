import json

import pytest

from automation.ci import slack


def test_chunk_message_short_message_returns_single_chunk_unchanged() -> None:
    message = "line1\nline2\nline3"

    chunks = slack.chunk_message(message, limit=2000)

    assert chunks == [message]


def test_chunk_message_splits_long_message_and_stays_under_limit() -> None:
    lines = [f"- #{i} some PR title padded out to be realistically long — url" for i in range(200)]
    message = "\n".join(lines)

    chunks = slack.chunk_message(message, limit=2000)

    assert len(chunks) > 1
    assert all(len(chunk) <= 2000 for chunk in chunks)


def test_chunk_message_never_breaks_a_line_mid_entry() -> None:
    lines = [f"- #{i} some PR title padded out to be realistically long — url" for i in range(200)]
    message = "\n".join(lines)

    chunks = slack.chunk_message(message, limit=2000)

    reconstructed = "\n".join(chunks)
    assert reconstructed == message


def test_post_to_slack_sends_text_field_to_webhook_url(
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

    monkeypatch.setattr(slack.urllib.request, "urlopen", _fake_urlopen)

    slack.post_to_slack("hello digest", "https://hooks.slack.example/webhook")

    assert captured["url"] == "https://hooks.slack.example/webhook"
    assert captured["body"] == {"text": "hello digest"}
    assert captured["headers"].get("user-agent", "").startswith("Python-urllib") is False
