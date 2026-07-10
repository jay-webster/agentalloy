"""Deterministic screen for content that looks like it's trying to instruct
the agent reading it, rather than just being newsletter prose about AI.

Pattern matching only, no LLM call -- a backstop that doesn't depend on the
agent noticing the manipulation itself. See docs/solutions/
automation-injection-guard.md for why this exists.
"""

from __future__ import annotations

import re

_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    (
        "ignore-previous-instructions",
        re.compile(r"ignore (all |any )?(previous|prior|above) instructions", re.I),
    ),
    ("disregard-above", re.compile(r"disregard (the )?(above|previous)", re.I)),
    ("new-instructions", re.compile(r"new instructions\s*:", re.I)),
    (
        "role-override",
        re.compile(r"you are now|act as if you|system (prompt|override)", re.I),
    ),
    (
        "direct-agent-address",
        re.compile(r"\b(AI|agent|assistant)\s*,?\s*(you must|you should|please)\b", re.I),
    ),
]


def screen(text: str) -> list[str]:
    return [name for name, pattern in _PATTERNS if pattern.search(text)]
