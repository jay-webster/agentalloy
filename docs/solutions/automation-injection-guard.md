# automation-injection-guard — Lesson

## Problem

Slice 2's live proof surfaced a real prompt-injection disclosure
("Agentjacking") describing an attack this very pipeline is exposed to: an
agent reading untrusted external content (newsletter email, in this case;
Sentry errors, in the disclosed research) that gets manipulated into taking
an unintended action. Before building the next slice (the integrator, which
would act on `accept` verdicts with real autonomy against agentalloy's own
repo), harden the foundation it would build on.

## What worked

**Naming the specific compounding risk instead of a generic "add security"
task.** The concrete framing — "this pipeline reads exactly the kind of
content the disclosed attack exploits, and the next slice adds the kind of
autonomous action that would make a successful attack expensive" — made the
scope obvious and bounded: screen the content that's actually stored and
actually cheap to check (subject/snippet at ingestion), and make the
riskiest single action (`accept`, which is what the integrator would act
on) structurally refuse to fire on flagged content. A vague "make it more
secure" task would have sprawled.

**A code-level guarantee instead of an instruction-level one.** The design
choice to have `evaluate()` itself raise on a flagged accept — not just tell
the routine "please don't accept flagged candidates" — means the backstop
holds even if the agent executing the routine is the thing being
manipulated. This is the actual point of defense in depth: don't rely
solely on the layer that's under attack to defend itself.

**Running the adversarial half of the live proof for real, not just in
unit tests.** Constructing an actual injection-shaped candidate and pushing
it through the real CLI against the real production database — watching it
get flagged, watching the accept attempt get refused with the exact
expected message, confirming no partial write happened — is meaningfully
different evidence than "the unit test asserts `pytest.raises`." It's the
same "prefer real verification" instinct applied to a safety mechanism
specifically, which is exactly where it matters most: a safety mechanism
that only works in tests but not in the real path is not a safety
mechanism.

## What didn't work / had to be corrected

Nothing required correction this slice — the design held on the first
implementation pass, and both live-proof directions passed on the first
run. Worth noting as a signal that scoping this as its own slice (rather
than folding it into the integrator, or skipping it) was the right call:
narrow, well-motivated scope was easy to implement and verify correctly the
first time.

## Decisions worth keeping

- When a live proof surfaces a finding that's relevant to the tool doing
  the evaluating (not just the thing being evaluated), treat it as
  actionable, not just interesting — this pipeline being exposed to the
  exact attack class it flagged in a candidate is a stronger signal than an
  abstract "coding agents in general are at risk."
- A safety/guardrail mechanism belongs at the layer that can't be talked
  out of enforcing it (code), with the agent-facing instruction layer as a
  second, complementary line of defense — not the only one.
- Sequence hardening before the slice that increases blast radius, not
  after. This was Jay's explicit call when scoping tonight's work, and it
  held up as the right call once the specific risk (an agent taking action
  based on untrusted content) was named concretely.
