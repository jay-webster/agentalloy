"""Classifies a PR's real changed paths for the auto-merge-gate workflow.

Thin CLI wrapper around the already-built, already-tested
`risk_classifier.classify()` -- gives the workflow a way to invoke it and
read back a `low`/`high` result. No new classification logic here.
"""

from __future__ import annotations

import sys

from automation.risk_classifier import classify


def main() -> int:
    changed_paths = [line for line in sys.stdin.read().splitlines() if line]
    print(classify(changed_paths))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
