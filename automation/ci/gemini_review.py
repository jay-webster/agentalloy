"""Has Gemini review a PR diff, for use as a GitHub Actions check.

Deliberately a different model family than whatever authored the diff --
reduces the correlated blind spots a same-model self-review would share
with the code it's reviewing.
"""

from __future__ import annotations

import json
import os
import re
import sys
import urllib.request
from typing import Any

GEMINI_MODEL = "gemini-flash-latest"  # alias for the current flash-tier model -- avoids
# repinning to a dated model name every time Google cycles versions (confirmed
# 2026-07-11: gemini-2.5-flash returned a live 404 despite being a valid model
# per this key's own ListModels response -- an alias sidesteps that class of
# failure going forward). Higher rate limits than *-pro; see docs/solutions/
# automation-gemini-review.md.
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


_FENCE_RE = re.compile(r"```(?:json)?\s*(.*?)\s*```", re.DOTALL)


def parse_response(raw_text: str) -> dict[str, Any]:
    text = raw_text.strip()
    # A real finding from this feature's own review of itself: only
    # stripping a fence when the response starts with it misses any
    # leading conversational text before the fence. Search for a fenced
    # block anywhere; fall back to the raw text if there isn't one.
    fence_match = _FENCE_RE.search(text)
    if fence_match:
        text = fence_match.group(1)
    try:
        return json.loads(text.strip())
    except json.JSONDecodeError as exc:
        raise ValueError(f"could not parse Gemini response as JSON: {raw_text!r}") from exc


def format_comment(review: dict[str, Any]) -> str:
    # .get() with fallbacks throughout: a real finding from this feature's
    # own first live-tested Gemini review -- direct key access would raise
    # KeyError if a future response ever deviates from the requested schema.
    verdict = review.get("verdict", "request_changes")
    verdict_label = "✅ Approved" if verdict == "approve" else "⚠️ Changes requested"
    summary = review.get("summary", "(no summary provided)")
    lines = [f"## Gemini Review — {verdict_label}", "", summary]
    findings = review.get("findings") or []
    if findings:
        lines.append("")
        lines.append("### Findings")
        for f in findings:
            severity = f.get("severity", "unknown")
            file = f.get("file", "?")
            description = f.get("description", "(no description)")
            lines.append(f"- **[{severity}]** `{file}`: {description}")
    return "\n".join(lines)


def call_gemini(prompt: str, api_key: str) -> str:
    # The key goes in a header, not the URL query string -- a URL is far more
    # likely to end up echoed in logs, proxies, or error tracebacks than a
    # header value (a real finding from this feature's own first live-tested
    # Gemini review, on this exact file).
    body = json.dumps({"contents": [{"parts": [{"text": prompt}]}]}).encode()
    req = urllib.request.Request(
        GEMINI_ENDPOINT,
        data=body,
        headers={"Content-Type": "application/json", "x-goog-api-key": api_key},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=120) as resp:
        data = json.loads(resp.read())
    candidates = data.get("candidates") or []
    if not candidates:
        raise ValueError(f"Gemini response had no candidates (possibly safety-filtered): {data!r}")
    return candidates[0]["content"]["parts"][0]["text"]


def main() -> int:
    # Everything is inside the try, not just the network call: a real
    # finding from this feature's own live review of itself -- reading
    # GEMINI_API_KEY/PR_TITLE outside the guard meant a missing env var
    # (e.g. secrets unavailable on a fork PR) would KeyError before the
    # "always leave a diagnostic comment" guarantee ever engaged.
    try:
        title = os.environ["PR_TITLE"]
        description = os.environ.get("PR_BODY", "")
        diff = sys.stdin.read()
        api_key = os.environ["GEMINI_API_KEY"]

        prompt = build_prompt(title, description, diff)
        raw = call_gemini(prompt, api_key)
        review = parse_response(raw)
    except Exception as exc:  # noqa: BLE001 -- must never leave the PR with no comment at all
        print(f"## Gemini Review — ⚠️ Review failed\n\nCould not complete: {exc}")
        return 1

    print(format_comment(review))
    return 0 if review.get("verdict") == "approve" else 1


if __name__ == "__main__":
    raise SystemExit(main())
