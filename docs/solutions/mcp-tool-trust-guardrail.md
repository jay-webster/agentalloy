# mcp-tool-trust-guardrail — Lesson

## Problem

Prove the automation pipeline's deferred integrator workflow — accept
verdict → draft intake → real SDD cycle → pushed branch — actually works,
by hand, before ever automating it into a routine. Use a real accepted
candidate as the subject, not synthetic data.

## What worked

**Choosing a candidate with a genuinely concrete, buildable target.** Of
the 9 real `needs_review` candidates, most (GLM 5.2, the loop-engineering
critique, the Managed Agents API article) were architectural reads, not
features — nothing to spec. The MCP security disclosure had an obvious,
concrete target (a corpus guardrail skill) from the moment it was
evaluated. Picking the right subject mattered more than the workflow
mechanics.

**The dry run immediately surfaced a real gap the design phase hadn't
anticipated.** The draft intake artifact's "Original content" section
turned out to only carry the store's thin `snippet` field, not the actual
article content fetched live during evaluation. This wasn't found by
inspection or a test — it was found by actually trying to use the draft
for its stated purpose. This is exactly the value of a manual dry run over
a synthetic proof: a synthetic candidate's snippet and "full content"
would have been the same thing by construction, hiding this gap entirely.

**Verifying the example fragment against real shipped code, not memory of
having written it.** The skill's worked example describes
`injection_guard.py`/`evaluate()`'s behavior; checking that description
against the actual merged code (not just recalling what was intended)
caught nothing wrong this time, but is the right habit regardless —
skill content that drifts from the code it cites becomes actively
misleading over time.

**Stopping at a pushed branch, deliberately, as the actual point of the
exercise.** The temptation in a dry run is to "finish the job" by opening
a PR too, since nothing is technically stopping it. Treating "stop here"
as the thing being tested — not a shortcut being taken — kept the exercise
honest about what it was actually proving: that the workflow respects the
human-review boundary, not just that it can produce a mergeable diff.

## What didn't work / had to be corrected

A typo (`sufond` for `sufficient`) made it into the first draft of the
`raw_prose` field and had to be caught by proofreading — `validate-pack`'s
consistency check only catches drift *between* `raw_prose` and fragments,
not errors present identically in both. Worth remembering: content
validation tooling checks structure, not correctness — a typo copied
consistently into both copies passes structural validation cleanly.

## Decisions worth keeping

- When picking a real subject for a dry run, prefer one with a concrete,
  buildable target over one that's merely "interesting" — an architectural
  read doesn't exercise the same workflow a concrete feature spec does.
- Run every "prove it end to end" exercise against real prior artifacts
  (the actual draft file, the actual shipped code) rather than assuming
  they say what they were designed to say — this is exactly the class of
  gap a synthetic test can't surface.
- When a workflow is deliberately scoped to stop short of some action, the
  dry run should prove *that it stops*, not just that it could go further.
