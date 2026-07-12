"""Posts a scheduled Discord digest of PR activity for this repo.

A pure formatting function buckets PRs into opened/merged/still-open;
one isolated impure function posts the result to a Discord webhook.
No dependency on automation-discord-notify's candidate-evaluation digest
-- different data source, different trigger, different concern.
"""

from __future__ import annotations

import json
import os
import sys
import urllib.request
from typing import Any


def _merge_label(pr: dict[str, Any]) -> str:
    merged_by = pr.get("mergedBy")
    if not merged_by:
        return "merged"
    return "auto-merged" if merged_by.get("is_bot") else "manually merged"


def format_digest(prs: list[dict[str, Any]], since: str) -> str:
    opened = [p for p in prs if p["createdAt"] >= since]
    merged = [p for p in prs if p.get("mergedAt") and p["mergedAt"] >= since]
    still_open = [p for p in prs if p["state"] == "OPEN"]

    if not opened and not merged and not still_open:
        return f"PR Digest — nothing to report since {since}."

    lines = [f"PR Digest — since {since}"]
    if opened:
        lines.append(f"\nOpened ({len(opened)}):")
        lines += [f"- #{p['number']} {p['title']} — {p['url']}" for p in opened]
    if merged:
        lines.append(f"\nMerged ({len(merged)}):")
        lines += [f"- #{p['number']} {p['title']} — {_merge_label(p)} — {p['url']}" for p in merged]
    if still_open:
        lines.append(f"\nStill open ({len(still_open)}):")
        lines += [f"- #{p['number']} {p['title']} — {p['url']}" for p in still_open]
    return "\n".join(lines)


def post_to_discord(message: str, webhook_url: str) -> None:
    body = json.dumps({"content": message}).encode()
    req = urllib.request.Request(
        webhook_url,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        resp.read()


def main() -> int:
    try:
        since = os.environ["SINCE"]
        webhook_url = os.environ["DISCORD_WEBHOOK_URL"]
        prs = json.loads(sys.stdin.read())
        message = format_digest(prs, since)
        post_to_discord(message, webhook_url)
    except Exception as exc:  # noqa: BLE001 -- always surface a clear diagnostic
        print(f"pr-digest failed: {exc}", file=sys.stderr)
        return 1

    print(message)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
