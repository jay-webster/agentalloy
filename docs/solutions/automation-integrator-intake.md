# automation-integrator-intake — Lesson

## Problem

Build the "act on accept" slice of the pipeline. The original pipeline
vision describes this as running agentalloy's full SDD lifecycle
unsupervised and opening a PR — but there was no real `accept` verdict yet
to build or test against, and jumping straight to full autonomy right
after a hardening slice would have undone the point of sequencing that
hardening first.

## What worked

**Treating "how far should this go" as its own scoping decision, not an
assumption.** The original vision's wording ("autonomously execute the
integration... and open a PR") could have been taken literally. Naming the
gap explicitly — this is a much bigger build than anything shipped so far,
and there's no real data to prove it against yet — turned an implicit
scope-creep risk into an explicit choice with a clear, narrow answer:
intake hand-off only, stop before any code change or PR.

**A code-level idempotency guarantee for the same reason slice 3 chose a
code-level enforcement over an instruction-level one.** Once a draft file
exists, a human may be actively editing it. `integrate()`'s idempotency
check happens strictly before any file write — not "regenerate and hope
nothing conflicts," but "check first, touch nothing if already done." This
is the same design instinct as slice 3's `FlaggedCandidateError` (a
structural guarantee, not a documented expectation), applied to a
different risk (destroying human work-in-progress instead of taking an
unauthorized action).

**Proving idempotency against a real file, not just an in-memory test.**
Writing distinguishable text directly into the generated draft file, then
re-running `integrate()`, then confirming that exact text survived
byte-for-byte on disk is a stronger proof than a unit test's mocked
filesystem — it's the actual property a human depends on ("my edits won't
get silently erased"), verified the way it would actually fail if the
design were wrong.

## What didn't work / had to be corrected

Nothing required correction — same as slice 3, the design held on first
implementation and all live-proof checks passed on the first run. Two
slices in a row landing clean on the first pass suggests the "narrow slice,
explicit assumptions, live proof before ship" rhythm established across
tonight's work is producing genuinely well-scoped units, not just fast
ones.

## Decisions worth keeping

- When an original spec/vision document describes something at a scope
  much larger than what's buildable and provable in one sitting, don't
  silently build a partial version and call it done — name the gap and
  scope explicitly to the hand-off point that *is* provable, leaving the
  rest as an explicit next step.
- A draft/generated artifact that a human is expected to edit needs its own
  explicit "don't clobber existing human work" guarantee, verified against
  the real filesystem — this is a distinct risk from "don't take an
  unauthorized action" (slice 3) and deserves its own explicit design
  attention, not an assumption that idempotency-by-convention is enough.
- Label synthetic/proof-only data unambiguously (sender addresses like
  `proof@synthetic.example`, explicit "Synthetic candidate" subjects) and
  clean it up after — the same practice from slice 3's adversarial proof,
  now used twice, worth treating as the standing pattern for any future
  slice that needs live-proof data it can't ethically manufacture from real
  records.
