"""Classifies a set of changed file paths as low or high blast-radius.

Deterministic gate for tiered autonomy: only a `low` classification is
ever eligible for auto-merge. Fails closed -- ambiguous or empty input is
`high`, never `low` by default. Does not decide to merge anything itself;
see automation/routines/ for how this feeds into an actual merge decision.
"""

from __future__ import annotations

from typing import Literal

LOW_RISK_PATH_PREFIXES = (
    "src/agentalloy/_packs/",
    "docs/",
)


def classify(changed_paths: list[str]) -> Literal["low", "high"]:
    if not changed_paths:
        return "high"
    if all(
        any(path.lstrip("./").startswith(prefix) for prefix in LOW_RISK_PATH_PREFIXES)
        for path in changed_paths
    ):
        return "low"
    return "high"
