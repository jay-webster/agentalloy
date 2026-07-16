"""Shared Discord-posting helpers: chunking and webhook delivery.

Extracted from pr_digest.py so pr-approved and digest-relay notifications
don't re-derive the same two hard-won details (the 2000-char content cap,
the mandatory non-default User-Agent).
"""

from __future__ import annotations

import json
import urllib.request

# Discord's documented hard limit on a single message's `content` field.
# A real finding from pr_digest.py's own live run: 19 real PRs in one
# window produced a 4590-char digest, and Discord's webhook API returned
# a bare 400 Bad Request rather than truncating -- the message-length
# safeguard this slice's own spec had deliberately deferred as
# low-probability became real the first time PR volume actually spiked.
DISCORD_MESSAGE_LIMIT = 2000


def chunk_message(message: str, limit: int = DISCORD_MESSAGE_LIMIT) -> list[str]:
    """Split on line boundaries into chunks each within Discord's limit.

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


def post_to_discord(message: str, webhook_url: str) -> None:
    body = json.dumps({"content": message}).encode()
    req = urllib.request.Request(
        webhook_url,
        data=body,
        # Discord's edge (Cloudflare) returns a bare 403 for requests using
        # urllib's default "Python-urllib/x.y" User-Agent -- a real finding
        # from pr_digest.py's own first live run against a real webhook.
        # Any identifiable, non-default UA clears it.
        headers={"Content-Type": "application/json", "User-Agent": "agentalloy-pr-digest/1.0"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        resp.read()
