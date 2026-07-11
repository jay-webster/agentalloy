import io

import pytest

from automation.ci import gemini_review


def test_build_prompt_includes_all_inputs_and_schema() -> None:
    prompt = gemini_review.build_prompt("My Title", "My description", "diff --git a/x.py")

    assert "My Title" in prompt
    assert "My description" in prompt
    assert "diff --git a/x.py" in prompt
    assert '"verdict"' in prompt


def test_parse_response_bare_json() -> None:
    raw = '{"verdict": "approve", "summary": "ok", "findings": []}'

    result = gemini_review.parse_response(raw)

    assert result == {"verdict": "approve", "summary": "ok", "findings": []}


def test_parse_response_markdown_fenced_json() -> None:
    raw = '```json\n{"verdict": "approve", "summary": "ok", "findings": []}\n```'

    result = gemini_review.parse_response(raw)

    assert result == {"verdict": "approve", "summary": "ok", "findings": []}


def test_parse_response_malformed_raises_value_error_with_raw_text() -> None:
    with pytest.raises(ValueError, match="not json at all"):
        gemini_review.parse_response("not json at all")


def test_format_comment_approve_no_findings() -> None:
    comment = gemini_review.format_comment(
        {"verdict": "approve", "summary": "looks good", "findings": []}
    )

    assert "Approved" in comment
    assert "looks good" in comment
    assert "Findings" not in comment


def test_format_comment_request_changes_with_finding() -> None:
    comment = gemini_review.format_comment(
        {
            "verdict": "request_changes",
            "summary": "issue found",
            "findings": [{"severity": "critical", "file": "x.py", "description": "bug"}],
        }
    )

    assert "Changes requested" in comment
    assert "issue found" in comment
    assert "critical" in comment
    assert "x.py" in comment
    assert "bug" in comment


def test_main_returns_zero_for_approve(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("PR_TITLE", "t")
    monkeypatch.setenv("PR_BODY", "d")
    monkeypatch.setenv("GEMINI_API_KEY", "fake-key")
    monkeypatch.setattr("sys.stdin", io.StringIO("diff text"))
    monkeypatch.setattr(
        gemini_review,
        "call_gemini",
        lambda prompt, api_key: '{"verdict": "approve", "summary": "ok", "findings": []}',
    )

    exit_code = gemini_review.main()

    assert exit_code == 0


def test_main_returns_nonzero_for_request_changes(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PR_TITLE", "t")
    monkeypatch.setenv("PR_BODY", "d")
    monkeypatch.setenv("GEMINI_API_KEY", "fake-key")
    monkeypatch.setattr("sys.stdin", io.StringIO("diff text"))
    monkeypatch.setattr(
        gemini_review,
        "call_gemini",
        lambda prompt, api_key: (
            '{"verdict": "request_changes", "summary": "bad", '
            '"findings": [{"severity": "major", "file": "y.py", "description": "issue"}]}'
        ),
    )

    exit_code = gemini_review.main()

    assert exit_code != 0
