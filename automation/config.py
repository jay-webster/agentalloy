"""Loads the newsletter-sender allowlist that defines what counts as an
"AI innovation" source — explicit and configured, never inferred by
classifying arbitrary inbox content.
"""

from __future__ import annotations

from pathlib import Path

import yaml

DEFAULT_SOURCES_PATH = Path("automation") / "config" / "sources.yaml"
EXAMPLE_SOURCES_PATH = Path("automation") / "config" / "sources.example.yaml"

SourceAllowlist = frozenset[str]


class SourcesConfigMissing(Exception):
    def __init__(self, path: Path) -> None:
        super().__init__(
            f"No sources config at {path}. Copy {EXAMPLE_SOURCES_PATH} to "
            f"{path} and edit it with your real newsletter senders."
        )


class SourcesConfigInvalid(Exception):
    def __init__(self, path: Path, bad_value: object) -> None:
        super().__init__(
            f"{path} must contain a YAML list of sender address/domain strings; "
            f"found an entry that isn't a string: {bad_value!r}"
        )


def load_sources(path: Path | None = None) -> SourceAllowlist:
    target = path if path is not None else DEFAULT_SOURCES_PATH
    if not target.exists():
        raise SourcesConfigMissing(target)

    raw = yaml.safe_load(target.read_text())
    if not isinstance(raw, list):
        raise SourcesConfigInvalid(target, raw)
    for entry in raw:
        if not isinstance(entry, str):
            raise SourcesConfigInvalid(target, entry)
    return frozenset(raw)
