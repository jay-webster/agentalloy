"""Posts a Discord notification the moment a PR is approved.

Complements pr_digest.py's daily rollup with immediate feedback. Uses the
same shared posting helpers from automation/ci/discord.py -- no duplicated
chunking/webhook logic.
"""

from __future__ import annotations

import json
import os
import sys
from typing import Any

from automation.ci.discord import post_to_discord

__all__ = ["format_approval_notice", "main"]


def format_approval_notice(pr: dict[str, Any], review: dict[str, Any]) -> str:
    reviewer = (review.get("user") or {}).get("login", "someone")
    return f"#{pr['number']} {pr['title']} approved by {reviewer} — {pr['url']}"


def main() -> int:
    try:
        pr = json.loads(os.environ["PR_JSON"])
        review = json.loads(os.environ["REVIEW_JSON"])
        webhook_url = os.environ["DISCORD_WEBHOOK_URL"]
        if not webhook_url:
            print("DISCORD_WEBHOOK_URL is not set -- skipping notification.")
            return 0
        message = format_approval_notice(pr, review)
        post_to_discord(message, webhook_url)
    except Exception as exc:  # noqa: BLE001 -- always surface a clear diagnostic
        print(f"pr-approved failed: {exc}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
