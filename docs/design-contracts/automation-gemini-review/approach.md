# automation-gemini-review — Design

## Approach

### 1. `gemini-2.5-pro`, REST API directly via `urllib`, no new dependency

**Decision.** `gemini-2.5-pro` — the strongest available model, matching
the actual point of this feature (a real second opinion, not a cheap
rubber stamp). Called via the plain REST `generateContent` endpoint using
stdlib `urllib.request`, not the `google-genai` SDK — this script runs in
an isolated GitHub Actions step, not the `automation/` package's own
dependency tree; avoiding a new dependency (and the SDK's own transitive
deps) keeps the Action's setup step trivial (`uv run python
automation/ci/gemini_review.py`, no separate `pip install` step needed
beyond what's already synced).

### 2. Structured-JSON prompt, tolerant parsing

**Decision.** The prompt instructs Gemini to return only a JSON object
matching a fixed schema (`verdict`, `summary`, `findings`). Real-world
model behavior sometimes wraps JSON in markdown code fences
(triple-backtick json blocks) despite instructions not to — `parse_response`
strips a leading/trailing fence before parsing, but does not attempt more
exotic recovery (extracting JSON from surrounding prose, retry-with-
different-prompt, etc.) — if the response is genuinely malformed beyond
fence-wrapping, raise a clear `ValueError` naming what was received,
rather than guessing. This mirrors `config.py`'s "fail loud and specific"
convention from earlier tonight, applied to a new kind of untrusted input
(a model's own output, not user config).

### 3. Four pure functions + one impure one, matching every prior slice's split

**Decision.**

```python
def build_prompt(title: str, description: str, diff: str) -> str: ...
def parse_response(raw_text: str) -> dict: ...
def format_comment(review: dict) -> str: ...
def call_gemini(prompt: str, api_key: str) -> str: ...  # the only impure one

def main() -> int:
    title = os.environ["PR_TITLE"]
    description = os.environ.get("PR_BODY", "")
    diff = sys.stdin.read()
    api_key = os.environ["GEMINI_API_KEY"]
    review = parse_response(call_gemini(build_prompt(title, description, diff), api_key))
    print(format_comment(review))
    return 0 if review["verdict"] == "approve" else 1
```

`call_gemini` is a thin, single-purpose wrapper (build the request, POST,
extract the text field from the response envelope) — kept separate so
tests can monkeypatch just that one function and exercise the full
`parse_response`/`format_comment` pipeline against a real (fixture)
Gemini response shape.

### 4. Workflow: plain PR comment, not the Reviews API

**Decision (resolves the spec's open design question).** `gh pr comment
<N> --body-file <output>` — a plain comment, not
`gh pr review --request-changes`/`--approve`. Simpler, and sufficient for
this slice's ACs (a visible, readable verdict). The GitHub Actions job's
own exit code (from the script's `main()` return value) is what makes this
show up as a real pass/fail check in the PR's checks list — the comment is
for human/agent readability, the exit code is what a future required-check
gate would actually key on.

The `post comment` step runs `if: always()` so the verdict gets posted
even when the review step exits non-zero (a `request_changes` verdict) —
the job as a whole should still show failed (so it can gate a required
check later), but the comment must still land.

## Non-goals carried from spec

No required-check wiring. No merge authority. No other model/provider. No
retry/rate-limit/cost handling.
