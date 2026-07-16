"""Extract candidate links from a newsletter body for follow-up fetching.

Pattern matching only, no I/O -- mirrors injection_guard.py's style. See
docs/design/newsletter-link-following/approach.md for why noise filtering
happens before the cap, and why this stays a pure function.
"""

from __future__ import annotations

import re

_URL_PATTERN = re.compile(r"https?://[^\s<>\"']+")

_TRAILING_PUNCTUATION = ",.);]'\""

_NOISE_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"unsubscribe", re.I),
    re.compile(r"privacy-?policy", re.I),
    re.compile(r"list-manage\.com|mailchimp", re.I),
    re.compile(r"(twitter|x)\.com/intent/|facebook\.com/sharer|linkedin\.com/sharing", re.I),
]


def _is_noise(url: str) -> bool:
    return any(pattern.search(url) for pattern in _NOISE_PATTERNS)


def extract_links(text: str, cap: int = 5) -> tuple[list[str], int]:
    seen: set[str] = set()
    links: list[str] = []
    skipped = 0

    for match in _URL_PATTERN.finditer(text):
        url = match.group(0).rstrip(_TRAILING_PUNCTUATION)
        if not url or url in seen or _is_noise(url):
            continue
        seen.add(url)
        if len(links) < cap:
            links.append(url)
        else:
            skipped += 1

    return links, skipped
