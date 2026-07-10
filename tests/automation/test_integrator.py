from automation.integrator import render_draft, slugify
from automation.store import Candidate


def _candidate() -> Candidate:
    return Candidate(
        message_id="19f4bdc8e71b738e",
        thread_id="thread-1",
        source="stayingahead@mail.beehiiv.com",
        subject="gpt 5.6 / grok 4.5 / glm 5.2",
        received_at="2026-07-10T11:49:33Z",
        snippet="and a lot more happened this week",
        ingested_at="2026-07-10T12:00:00Z",
        status="evaluated",
        verdict="accept",
        rationale="GLM 5.2 is a real open-weight model finding.",
    )


def test_slugify_is_deterministic_with_message_id_suffix() -> None:
    slug = slugify("OpenAI Is Building an AI Superapp", "19f4c1c888d64b0d")

    assert slug == slugify("OpenAI Is Building an AI Superapp", "19f4c1c888d64b0d")
    assert slug.endswith("19f4c1c8")
    assert slug.startswith("openai-is-building-an-ai")


def test_slugify_differs_for_different_message_ids_same_subject() -> None:
    first = slugify("Same Subject", "aaaaaaaa1111")
    second = slugify("Same Subject", "bbbbbbbb2222")

    assert first != second


def test_render_draft_includes_all_required_fields() -> None:
    candidate = _candidate()
    slug = slugify(candidate.subject, candidate.message_id)

    draft = render_draft(candidate, slug)

    assert candidate.subject in draft
    assert candidate.source in draft
    assert candidate.rationale in draft
    assert candidate.snippet in draft
    assert f"agentalloy contract init --phase spec --slug {slug}" in draft
