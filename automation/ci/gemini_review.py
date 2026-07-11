"""Has Gemini review a PR diff, for use as a GitHub Actions check.

Deliberately a different model family than whatever authored the diff --
reduces the correlated blind spots a same-model self-review would share
with the code it's reviewing.
"""

from __future__ import annotations

import json
import os
import sys
import urllib.request
from typing import Any

GEMINI_MODEL = "gemini-2.5-pro"
GEMINI_ENDPOINT = (
    f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent"
)

_PROMPT_TEMPLATE = """You are reviewing a pull request diff for correctness, security, and code quality issues. You are intentionally a different model than whatever wrote this code, specifically to catch issues a same-model self-review might miss.

PR Title: {title}
PR Description: {description}

Diff:
{diff}

Respond with ONLY a JSON object matching this schema, no other text, no markdown formatting:
{{"verdict": "approve" or "request_changes", "summary": "1-2 sentence overall assessment", "findings": [{{"severity": "critical" or "major" or "minor", "file": "path", "description": "..."}}]}}

Use "request_changes" if there are any critical or major findings. Use "approve" if the diff is correct and safe, even if there are minor stylistic notes."""


def build_prompt(title: str, description: str, diff: str) -> str:
    return _PROMPT_TEMPLATE.format(title=title, description=description, diff=diff)


def parse_response(raw_text: str) -> dict[str, Any]:
    text = raw_text.strip()
    if text.startswith("```"):
        text = text.split("```")[1]
        if text.startswith("json"):
            text = text[len("json") :]
    try:
        return json.loads(text.strip())
    except json.JSONDecodeError as exc:
        raise ValueError(f"could not parse Gemini response as JSON: {raw_text!r}") from exc


def format_comment(review: dict[str, Any]) -> str:
    verdict_label = "✅ Approved" if review["verdict"] == "approve" else "⚠️ Changes requested"
    lines = [f"## Gemini Review — {verdict_label}", "", review["summary"]]
    findings = review.get("findings") or []
    if findings:
        lines.append("")
        lines.append("### Findings")
        for f in findings:
            lines.append(f"- **[{f['severity']}]** `{f['file']}`: {f['description']}")
    return "\n".join(lines)


def call_gemini(prompt: str, api_key: str) -> str:
    body = json.dumps({"contents": [{"parts": [{"text": prompt}]}]}).encode()
    req = urllib.request.Request(
        f"{GEMINI_ENDPOINT}?key={api_key}",
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=120) as resp:
        data = json.loads(resp.read())
    return data["candidates"][0]["content"]["parts"][0]["text"]


def main() -> int:
    title = os.environ["PR_TITLE"]
    description = os.environ.get("PR_BODY", "")
    diff = sys.stdin.read()
    api_key = os.environ["GEMINI_API_KEY"]

    prompt = build_prompt(title, description, diff)
    try:
        raw = call_gemini(prompt, api_key)
        review = parse_response(raw)
    except Exception as exc:  # noqa: BLE001 -- must never leave the PR with no comment at all
        print(f"## Gemini Review — ⚠️ Review failed\n\nCould not complete: {exc}")
        return 1

    print(format_comment(review))
    return 0 if review["verdict"] == "approve" else 1


if __name__ == "__main__":
    raise SystemExit(main())
