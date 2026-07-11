# automation-gemini-review — Lesson

## Problem

Jay wants an independent, different-model-family code review as part of
the auto-merge safety net — using a model that didn't write the code to
catch issues correlated with whatever model did.

## What worked

**Treating the API key with more caution than the Discord webhook URL
earlier tonight, and being explicit about why.** A webhook URL is scoped
to "post messages to one channel" — low blast radius, easily revocable. A
Gemini API key is a broader, billable credential. Rather than applying a
uniform rule, this session distinguished the two and chose the more
conservative path for the higher-stakes credential: never ask Jay to paste
it into the conversation, verify success via the workflow run's outcome
only (which GitHub redacts automatically), not by handling the value
directly.

**Reusing the exact same deterministic/impure split as every prior
external-integration slice.** `build_prompt`/`parse_response`/
`format_comment` are pure and fully tested; `call_gemini` is the one
function that touches the network, isolated specifically so tests can
monkeypatch it without needing a real key. This is now the fourth or fifth
time this exact pattern has paid off (Apps Script export, Discord webhook,
now Gemini) — worth recognizing as the house style for "integrate with an
external service" work in this pipeline, not something to re-derive each
time.

**Catching the real strict-mode gap during the actual typecheck step, not
skipping it because "it's just two dict annotations."** Bare `dict` return
types failed `reportMissingTypeArgument` — an easy thing to wave off as
pedantic, but running the real gate caught it before it could compound.

**Using the feature to review its own source, repeatedly.** Once the
workflow was live, every real push re-triggered Gemini reviewing
`gemini_review.py` and `gemini-review.yml` themselves. This produced three
separate rounds of genuine, non-obvious findings (API key in URL vs.
header; unguarded dict access; and later, env-var reads outside the
try/except, a fence-stripping edge case, and a missing-file guard in the
workflow) — the single strongest piece of evidence in this whole session
that different-model review actually catches things same-model review
plausibly wouldn't.

## What didn't work / had to be corrected

- The bare-`dict` type annotation gap (see above) — caught by the tool
  doing its job, not a process failure.
- **A `pipefail`-less `tee` produced a false-positive pass while the
  script was actually crashing.** `python script.py | tee file` reports
  `tee`'s exit code (always 0), not the script's. This would have silently
  defeated the entire point of the check as a future auto-merge gate — a
  broken reviewer would report "pass" forever. Any CI step piping a
  script's output through `tee` (or any second command) needs
  `set -o pipefail` as a first line, unconditionally.
- **A later fix reintroduced an earlier-fixed bug class.** Round 1 fixed a
  silent crash by wrapping `call_gemini` in try/except. Round 2's edit
  (switching the API key to a header) touched `main()` again and, in the
  process, left the env-var reads (`os.environ["PR_TITLE"]`,
  `os.environ["GEMINI_API_KEY"]`) sitting *outside* the try block — the
  exact same silent-crash shape as the original bug, just relocated.
  Round 3's live review caught it. Lesson: a fix that touches a function
  already hardened against a specific failure mode needs a re-check that
  the hardening still covers the whole function, not just a diff-local
  review of the new lines.

## Decisions worth keeping

- Not every credential deserves the same handling — weigh actual blast
  radius (a scoped webhook vs. a billable, account-wide API key) and
  choose the more conservative path for the higher-stakes one, rather than
  applying one uniform rule to all "secrets."
- When verifying a credential-gated integration works, verify via an
  outcome that can't leak the credential (a workflow run's pass/fail
  conclusion) rather than needing to see or handle the credential's value
  directly — this is usually possible if you design the verification step
  for it up front.
- The pure-functions-plus-one-isolated-impure-call shape, once it's worked
  three or four times running, is worth reaching for by default on the
  next external integration rather than re-deriving the split each time.
- Prefer a `-latest`/stable model alias over a dated, pinned model name for
  anything long-running — a pinned name going stale (404ing despite being
  listed as valid) is now a repeated, confirmed failure mode, not a
  one-off.
- A check whose own job status can be silently wrong (the `pipefail` bug)
  is worse than no check at all, because it creates false confidence.
  Before trusting any new CI gate's pass/fail as meaningful, deliberately
  force a real failure through it once and confirm the job actually goes
  red.
