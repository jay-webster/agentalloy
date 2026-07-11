# Automation Gemini Review — Spec

> **Scope in a sentence.** A GitHub Actions check that has Gemini review
> every PR's diff and report a pass/fail verdict — an independent,
> different-model-family second opinion that becomes part of the safety
> net gating tiered autonomy, alongside the risk classifier.

> **Location note.** At runtime the SDD spec phase writes the spec to
> `docs/spec/automation-gemini-review.md`, git-ignored. This file is the
> committed, reviewable copy.

## Context

Jay's explicit request: use his existing Gemini API access for code
review, citing the real, documented practice that a different model
family reviewing a diff catches issues correlated with whatever model
wrote it — the same model grading its own homework shares blind spots.
This becomes a second, independent layer in the auto-merge safety net
being built toward tonight, alongside `automation/risk_classifier.py`
(slice 7): the risk classifier answers "is this change low-blast-radius
enough to ever be eligible," a Gemini review answers "does this specific
diff actually look correct" — two different questions, both real signal.

This slice is scoped narrower than "wire everything into auto-merge" —
consistent with every prior slice tonight, prove the piece, don't
assume the whole system. GitHub Actions was confirmed enabled on the fork
moments before this slice started (a still-unconfirmed fork-specific
banner may remain — see project memory), so this slice's live proof
depends on that being fully resolved.

## Assumptions (correct these before design)

- **The Gemini API key is never handled in this session's conversation.**
  Jay adds it as a GitHub Actions repository secret himself (a command
  this session provides, but Jay runs it); the workflow references
  `secrets.GEMINI_API_KEY`. This session verifies success by inspecting
  the resulting workflow run's outcome (GitHub redacts secret values from
  logs automatically), never by seeing or logging the key itself.
- **Deterministic parts are separated from the live API call**, same split
  every prior slice has used: prompt construction, response parsing, and
  comment formatting are pure functions, fully unit-testable without
  network access; only the actual Gemini call itself is untestable without
  live credentials.
- **The review is advisory input to a required check, not a merge
  decision by itself.** This slice produces a pass/fail signal and a
  posted comment; it does not merge or block anything on its own — wiring
  it into branch protection's required checks (so it actually gates
  merges) is explicitly deferred, matching how `risk_classifier.py`
  computes an answer without yet acting on it.
- **Runs on every PR**, not just automation-pipeline-originated ones —
  this is repo-wide CI infrastructure, matching the shape of the existing
  `ci.yml`'s trigger.

## What

**Review script.** `automation/ci/gemini_review.py`:
`build_prompt(title, description, diff) -> str` (constructs the review
prompt), `parse_response(raw_text) -> dict` (extracts the structured
verdict from Gemini's response text, tolerating markdown code-fence
wrapping), `format_comment(review) -> str` (renders a PR-comment-ready
string), and `call_gemini(prompt, api_key) -> str` (the one function that
makes a real network call). A `main()` wires these together, reading PR
title/body from environment variables, the diff from stdin, and the API
key from `GEMINI_API_KEY`; exits non-zero when the verdict is
`request_changes`, printing the formatted comment either way.

**GitHub Actions workflow.** `.github/workflows/gemini-review.yml` —
triggers on `pull_request` (opened, synchronize, reopened), matching
`ci.yml`'s trigger shape; checks out the PR, computes the diff, runs the
script with `secrets.GEMINI_API_KEY`, posts the output as a PR comment via
`gh pr comment`, and fails the job (non-zero exit) when the script does,
so the run shows as a real pass/fail check.

## Acceptance Criteria

1. **`build_prompt` produces a well-formed prompt** including the title,
   description, and diff verbatim, plus the structured-JSON response
   instruction. Verifiable by a unit test.
2. **`parse_response` handles both raw JSON and markdown-fenced JSON**
   (Gemini's actual behavior varies) and raises a clear error on genuinely
   malformed output rather than crashing opaquely. Verifiable by unit
   tests covering both wrapped and unwrapped cases, plus a malformed-input
   case.
3. **`format_comment` renders both verdicts distinctly** (`approve` vs.
   `request_changes`) and includes every finding when present, omits the
   findings section when empty. Verifiable by unit tests for both
   verdicts.
4. **`main()`'s exit code matches the verdict**: 0 for `approve`, non-zero
   for `request_changes` — this is what makes the GitHub Actions job
   itself report pass/fail. Verifiable by a unit test mocking
   `call_gemini`.
5. **No product code touched, no change to the automation pipeline's
   existing modules.** Zero diff under `src/agentalloy/` and under
   `automation/store.py`, `automation/cli.py`,
   `automation/injection_guard.py`, `automation/integrator.py`,
   `automation/risk_classifier.py`.
6. **The API key never appears in this session's conversation or in any
   committed file.** Verifiable by inspection — no key value anywhere in
   the diff, the workflow file references `secrets.GEMINI_API_KEY` only.
7. **Live proof**: once Jay confirms the secret is set, a real PR (this
   slice's own) triggers the workflow, and the resulting GitHub Actions
   run's outcome (visible via `gh run view`, logs redacted by GitHub) is
   inspected to confirm the workflow actually executed, called the real
   API, and reported a real pass/fail — not just that the YAML is
   syntactically present.

## Out of Scope

- **Wiring this into branch protection's required checks** — a real,
  separate action (GitHub repo settings), deferred until this check is
  proven reliable across a few real runs.
- **Making the review verdict authoritative over merge/no-merge** — it
  reports; nothing acts on the report yet.
- **Any other CI provider or model** — Gemini only, per Jay's explicit
  request.
- **Retrying on transient API failures, rate-limit handling, or cost
  controls** — a real production concern eventually, not solved in this
  first slice.

## Design surface (hand-off to the design phase)

- **Which Gemini model** — `gemini-2.5-pro` (higher quality, matches "a
  strong second opinion") vs. a faster/cheaper model — pick one, document
  why, easy to change later since it's one constant.
- **Comment vs. GitHub Review API** — posting a plain PR comment
  (`gh pr comment`) vs. using the Reviews API to leave an actual
  approve/request-changes review. A plain comment is simpler and
  sufficient for this slice's ACs; the Reviews API is a natural upgrade
  once this is proven.
