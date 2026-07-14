"""Relays a dispatched digest report to Discord.

Invoked by discord-digest-relay.yml on a repository_dispatch event: the
report text arrives pre-formatted via REPORT (set from
github.event.client_payload.report), so this module has no formatting
logic of its own -- just chunking and posting, via the shared helpers in
automation/ci/discord.py.
"""

from __future__ import annotations

import os
import sys

from automation.ci.discord import chunk_message, post_to_discord

__all__ = ["main"]


def main() -> int:
    try:
        report = os.environ["REPORT"]
        webhook_url = os.environ["DISCORD_WEBHOOK_URL"]
        if not webhook_url:
            print("DISCORD_WEBHOOK_URL is not set -- skipping relay.")
            return 0
        for chunk in chunk_message(report):
            post_to_discord(chunk, webhook_url)
    except Exception as exc:  # noqa: BLE001 -- always surface a clear diagnostic
        print(f"discord-relay failed: {exc}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
