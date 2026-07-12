# automation-evaluator-four-lens — Lesson

## Problem

The evaluator's two-lens framework (`evaluate-candidate.md`, from slice 2)
was flagged as incomplete in its own QA report the night it shipped: real
`needs_review` verdicts kept firing on content that was clearly relevant
but matched neither named lens ("feature fit" or "embed/reranker
replacement"). The question was left open rather than guessed at, pending
more real evidence.

## What worked

**Waiting for real evidence instead of speculatively designing a third
lens up front.** By the time this was revisited, 10 real `needs_review`
verdicts existed across several evaluation sessions. Reading all 10
rationales together (not just the ones remembered from earlier in the
session) surfaced a clean, non-obvious split:

- 4 were **local-model candidates the lens wording was too narrow to
  catch** — GLM 5.2, Qwen3.6/NVFP4 (x2), and a cost-efficiency tool all
  targeted a local-model surface, just not specifically the embed model
  or reranker (the actual target: the LM Studio model backing
  agentalloy's bulk-authoring pipeline, a real local-model surface the
  original lens wording never named).
- 2 were about **this automation pipeline's own architecture**, not
  agentalloy the product at all — a critique of autonomous coding-agent
  loop reliability, and a Managed Agents API tutorial paralleling this
  pipeline's own scheduling/state design.
- 4 were **not a framework gap at all** — unfetched content (full-body
  fetch failed or wasn't attempted) marked `needs_review` on sender
  reputation alone, not because any lens fired ambiguously. This had been
  quietly conflated with "lens didn't fire" in earlier rationales, which
  made the framework look weaker than it actually was.

That's real, load-bearing evidence for exactly two new/widened lenses
(local-model, widened; pipeline-self-architecture, new) plus a third,
named-but-not-fully-tested category (security/governance — validated by
one real historical case, the MCP/Agentjacking disclosure that became
slice 3's guardrail skill, even though it wasn't sitting unresolved in
`needs_review` at the time of this analysis).

## What didn't work / had to be corrected

The original framework's "neither lens fires → reject" rule was never
actually followed in practice — every real ambiguous-but-substantive item
got `needs_review` via judgment override, not `reject`. The written rule
and the actual behavior had quietly diverged. Fixed by making the
fallback explicit in the routine itself (see step 4's last bullet) instead
of leaving it as an unwritten judgment call that happened to always go
one way.

## Decisions worth keeping

- When a framework/heuristic feels incomplete, let real usage accumulate
  evidence before redesigning it — 10 real data points produced a much
  more precise fix than the original slice's speculative "maybe add a
  security lens" guess would have.
- Separate "the framework doesn't cover this" from "we don't have enough
  information to judge this" — they look identical in a `needs_review`
  pile but need different fixes (widen the framework vs. improve content
  fetching), and conflating them hides how well the framework is actually
  doing.
- A routine (markdown runbook) can and should evolve the same way code
  does — via real evidence, not just at design time — even though it has
  no test suite to enforce correctness. The proof here was retroactive:
  checking that all 10 historical `needs_review` items would now resolve
  cleanly under the new lenses, before committing to the change.
