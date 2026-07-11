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

## What didn't work / had to be corrected

The bare-`dict` type annotation gap (see above) — caught by the tool doing
its job, not a process failure.

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
