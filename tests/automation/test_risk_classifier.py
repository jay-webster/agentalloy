from automation.risk_classifier import LOW_RISK_PATH_PREFIXES, classify


def test_all_allowlisted_paths_classify_low() -> None:
    result = classify(["src/agentalloy/_packs/core/x.yaml", "docs/y.md"])

    assert result == "low"


def test_one_disallowed_path_makes_whole_change_high() -> None:
    result = classify(["src/agentalloy/_packs/core/x.yaml", "automation/store.py"])

    assert result == "high"


def test_all_disallowed_paths_classify_high() -> None:
    result = classify(["src/agentalloy/retrieval/hybrid.py"])

    assert result == "high"


def test_empty_input_classifies_high() -> None:
    result = classify([])

    assert result == "high"


def test_low_risk_path_prefixes_contents() -> None:
    assert set(LOW_RISK_PATH_PREFIXES) == {"src/agentalloy/_packs/", "docs/"}
