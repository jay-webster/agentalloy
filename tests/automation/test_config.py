from pathlib import Path

import pytest
from automation.config import (
    SourcesConfigInvalid,
    SourcesConfigMissing,
    load_sources,
)


def test_load_sources_returns_frozenset_of_entries(tmp_path: Path) -> None:
    config_path = tmp_path / "sources.yaml"
    config_path.write_text("- alice@example.com\n- bob@example.com\n")

    result = load_sources(path=config_path)

    assert result == frozenset({"alice@example.com", "bob@example.com"})


def test_missing_config_names_the_example_file(tmp_path: Path) -> None:
    missing_path = tmp_path / "sources.yaml"

    with pytest.raises(SourcesConfigMissing) as exc_info:
        load_sources(path=missing_path)

    assert "sources.example.yaml" in str(exc_info.value)


def test_malformed_config_identifies_the_bad_value(tmp_path: Path) -> None:
    config_path = tmp_path / "sources.yaml"
    config_path.write_text("alice: not-a-list\n")

    with pytest.raises(SourcesConfigInvalid) as exc_info:
        load_sources(path=config_path)

    assert "not-a-list" in str(exc_info.value) or "alice" in str(exc_info.value)


def test_malformed_config_with_non_string_entry(tmp_path: Path) -> None:
    config_path = tmp_path / "sources.yaml"
    config_path.write_text("- alice@example.com\n- 42\n")

    with pytest.raises(SourcesConfigInvalid) as exc_info:
        load_sources(path=config_path)

    assert "42" in str(exc_info.value)
