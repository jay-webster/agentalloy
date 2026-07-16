from automation.link_extract import extract_links


def test_multiple_distinct_links_extracted_in_order() -> None:
    body = (
        "Check out https://example.com/a and also "
        "https://example.com/b plus https://example.com/c"
    )

    links, skipped = extract_links(body)

    assert links == [
        "https://example.com/a",
        "https://example.com/b",
        "https://example.com/c",
    ]
    assert skipped == 0


def test_duplicate_links_deduped() -> None:
    body = "See https://example.com/a again: https://example.com/a"

    links, skipped = extract_links(body)

    assert links == ["https://example.com/a"]
    assert skipped == 0


def test_cap_enforcement_with_skipped_count() -> None:
    body = " ".join(f"https://example.com/{i}" for i in range(8))

    links, skipped = extract_links(body, cap=5)

    assert links == [f"https://example.com/{i}" for i in range(5)]
    assert skipped == 3


def test_noise_filtered_before_cap_applied() -> None:
    body = (
        "https://example.com/article-one "
        "https://example.com/article-two "
        "https://example.com/unsubscribe?id=123 "
        "https://example.com/privacy-policy "
        "https://us1.list-manage.com/track?id=456 "
        "https://twitter.com/intent/tweet?text=hi"
    )

    links, skipped = extract_links(body, cap=5)

    assert links == [
        "https://example.com/article-one",
        "https://example.com/article-two",
    ]
    assert skipped == 0


def test_zero_link_body_returns_empty() -> None:
    links, skipped = extract_links("Just plain newsletter prose, no links here.")

    assert links == []
    assert skipped == 0


def test_malformed_url_fragment_does_not_raise() -> None:
    body = "Broken link: http:// and truncated https://exam"

    links, skipped = extract_links(body)

    assert links == ["https://exam"]
    assert skipped == 0


def test_trailing_punctuation_stripped() -> None:
    body = (
        "Read this (https://example.com/a), then this https://example.com/b. "
        "Also this https://example.com/c!"
    )

    links, skipped = extract_links(body)

    assert links == [
        "https://example.com/a",
        "https://example.com/b",
        "https://example.com/c!",
    ]
