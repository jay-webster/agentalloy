# authoring-critic-model-setup-docs — Lesson

## Problem

The authoring pipeline's critic step runs a different model
(`critic_model`, `qwen3.6-27b`) from the author/revise steps
(`model`, `qwen3-14b-instruct`), on a separate LM Studio port
(`lm_studio_base_url` vs `lm_base_url`). None of this was written down
anywhere a new operator on Apple Silicon could find it — just the env-var
table and the code that reads it.

## What worked

**Verifying every claim against the running code instead of writing from
memory.** Each field in `AuthoringConfig` was read directly and matched
field-by-field against what the doc would claim, and each call site
(`authoring/pipeline.py`, `authoring/driver.py`, `authoring/__main__.py`)
was checked to confirm which config field each pipeline step actually
uses — so the "author uses X, critic uses Y" split documented is a fact
observed in the code, not an inference from naming.

**Live-checking the Hugging Face links instead of trusting them from
research notes.** All three model links were curled directly and
confirmed `200` before being committed to docs — a dead or renamed link
in setup instructions is worse than no link, since it costs the next
operator a debugging detour before they even start.

**Scoping the claim explicitly instead of implying universality.**
The subsection states up front that it's verified against a 48GB M4 Pro
Mac Mini and that non-Apple-Silicon guidance doesn't exist yet, rather
than writing generically and letting a CUDA user assume it applies to
them.

## What didn't

Nothing of substance — this was a small, precisely-scoped docs-only
change (one file, 37 insertions) where every acceptance criterion was
directly verifiable, so there wasn't a wrong turn to record.

## Worth keeping

Setup docs for a model/config split should always name *which pipeline
step* reads *which config field*, with real file:line references — a
generic "there are two models" note doesn't help the next person actually
debug a misconfigured step.
