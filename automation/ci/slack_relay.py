"""Relays a pre-formatted digest report to Slack.

Invoked directly by automation/routines/scheduled-drive-sync.md's step 4
(REPORT and SLACK_WEBHOOK_URL set as env vars ahead of the call) -- this
module has no formatting logic of its own, just chunking and posting, via
the shared helpers in automation/ci/slack.py. Previously invoked by a
GitHub Actions workflow (slack-digest-relay.yml) on a repository_dispatch
event; that relay was retired 2026-08-03 once direct Slack egress from
the routine's own sandbox was confirmed to work (see the routine doc's
Notes section).
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
