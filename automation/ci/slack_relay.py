"""Relays a dispatched digest report to Slack.

Invoked by slack-digest-relay.yml on a repository_dispatch event: the
report text arrives pre-formatted via REPORT (set from
github.event.client_payload.report), so this module has no formatting
logic of its own -- just chunking and posting, via the shared helpers in
automation/ci/slack.py.
"""

from __future__ import annotations

import os
import sys

from automation.ci.slack import chunk_message, post_to_slack

__all__ = ["main"]


def main() -> int:
    try:
        report = os.environ["REPORT"]
        webhook_url = os.environ["SLACK_WEBHOOK_URL"]
        if not webhook_url:
            print("SLACK_WEBHOOK_URL is not set -- skipping relay.")
            return 0
        for chunk in chunk_message(report):
            post_to_slack(chunk, webhook_url)
    except Exception as exc:  # noqa: BLE001 -- always surface a clear diagnostic
        print(f"slack-relay failed: {exc}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
