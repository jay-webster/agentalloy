# automation-evaluator — Lesson

## Problem

Given slice 1's backlog of ingested newsletter candidates, record a verdict
on each: worth integrating into agentalloy, not worth it, or genuinely
unclear. The store/CLI half was straightforward; the interesting part was
actually running the judgment call for real against 31 live candidates.

## What worked

**Running the live proof for real, and reporting the honest result (0
accept) instead of reaching for a positive-looking number.** A month of
general AI-industry newsletters is mostly noise for a specific tool like
agentalloy — that's a true, useful finding, and forcing an "accept" verdict
somewhere to make the demo look more successful would have been dishonest
and would have degraded the store's actual value as a triage tool. The
value this slice proved is accurate *triage*, not a high accept rate.

**Fetching full message bodies for a few high-signal-looking candidates,
falling back to snippet-only for the rest.** 4 of 31 candidates got a real
Gmail `get_message` fetch (chosen because their subjects suggested
technical specificity, not newsy vagueness); the other 27 were judged from
subject+snippet, matching the design's documented best-effort fallback.
This produced two genuinely valuable finds (an MIT-licensed open-weight
model beating GPT-5.5 on coding benchmarks; a real MCP/coding-agent RCE
disclosure) that a snippet-only pass would likely have missed or
under-weighted.

**Using observed sender signal quality as evidence, not just each
candidate in isolation.** After the CTO Mode newsletter's two fetched
issues both turned out to have substantive, non-obvious content well beyond
their snippets, the remaining unfetched CTO Mode issues were marked
`needs_review` rather than `reject` — an evidence-based adjustment, not a
guess, and stated explicitly as such in each rationale so it's auditable
later.

## What didn't work / had to be corrected

**The two-lens framework (feature fit, local-model-replacement fit) turned
out to be incomplete.** Several of the most genuinely valuable candidates
this run — a coding-agent security disclosure, a critique of autonomous
agent loops directly relevant to this pipeline's own design — didn't
cleanly fit either lens. The honest move was recording them as
`needs_review` with that gap stated explicitly in the rationale and QA
report, not forcing a fit to make the two-lens model look complete. This is
now an open question for whoever designs the next evaluator iteration: add
a third lens, or treat "doesn't fit, but seems important" as what
`needs_review` is *for* by design. Recorded, not resolved — resolving it
without more of Jay's input would be scope creep on this slice.

## Decisions worth keeping

- When a live proof run's real result could be spun as more impressive by
  fudging a verdict, report the honest result and explain *why* it's
  honest (general newsletters vs. a specific tool) rather than reaching for
  a better-looking number.
- A "doesn't fit our framework" observation during a live proof is a
  finding worth writing down (QA report + lesson), not a problem to paper
  over by force-fitting the nearest category.
- Evidence gathered mid-run (a sender's demonstrated signal quality) is a
  legitimate input to later judgment calls in the same run, as long as it's
  stated explicitly rather than silently baked in.
