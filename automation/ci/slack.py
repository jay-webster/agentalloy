"""Shared Slack-posting helpers: chunking and webhook delivery.

Ported from automation/ci/discord.py -- Discord is retired as the
notification channel; Slack's incoming-webhook API expects a `text` field
rather than `content`, and doesn't share Discord's hard 2000-char cap, but
this module keeps a conservative chunking safety net anyway so the
hard-won lesson from that Discord overflow incident (19 PRs -> a bare 400)
isn't quietly re-learned against a different provider.
"""

from __future__ import annotations

import json
import urllib.request

# Conservative chunk size for Slack's webhook `text` field. Slack tolerates
# far more than Discord's hard 2000-char cap, but chunking is kept as a
# safety net rather than assuming no limit exists.
SLACK_MESSAGE_LIMIT = 3000


def chunk_message(message: str, limit: int = SLACK_MESSAGE_LIMIT) -> list[str]:
    """Split on line boundaries into chunks each within Slack's limit.

    Never breaks a PR entry mid-line. A message already under the limit
    returns as a single chunk, reconstructing the original unchanged.
    """
    lines = message.split("\n")
    chunks: list[str] = []
    current: list[str] = []
    current_len = 0
    for line in lines:
        added_len = len(line) + (1 if current else 0)
        if current and current_len + added_len > limit:
            chunks.append("\n".join(current))
            current = [line]
            current_len = len(line)
        else:
            current.append(line)
            current_len += added_len
    if current:
        chunks.append("\n".join(current))
    return chunks


def post_to_slack(message: str, webhook_url: str) -> None:
    body = json.dumps({"text": message}).encode()
    req = urllib.request.Request(
        webhook_url,
        data=body,
        headers={"Content-Type": "application/json", "User-Agent": "agentalloy-pr-digest/1.0"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        resp.read()
