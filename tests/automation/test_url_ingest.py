from automation.url_ingest import candidate_id_for_url


def test_same_url_twice_returns_identical_id() -> None:
    url = "https://example.com/a"

    assert candidate_id_for_url(url) == candidate_id_for_url(url)


def test_trailing_slash_variant_collapses_to_same_id() -> None:
    assert candidate_id_for_url("https://example.com/a") == candidate_id_for_url(
        "https://example.com/a/"
    )


def test_distinct_urls_yield_distinct_ids() -> None:
    assert candidate_id_for_url("https://example.com/a") != candidate_id_for_url(
        "https://example.com/b"
    )
