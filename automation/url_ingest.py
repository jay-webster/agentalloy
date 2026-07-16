"""Content-addressed candidate IDs for Discord-sourced (and future manual) URLs.

Pure function, no I/O -- see docs/design/discord-inbound-link-ingestion/approach.md
section 1 for why this is a separate scheme (`url-{hash12}`) from the legacy
`manual-url-{hash12}` rows rather than a migration.
"""

from __future__ import annotations

import hashlib


def candidate_id_for_url(url: str) -> str:
    normalized = url.strip().rstrip("/")
    digest = hashlib.sha256(normalized.encode()).hexdigest()[:12]
    return f"url-{digest}"
