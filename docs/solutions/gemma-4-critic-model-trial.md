# gemma-4-critic-model-trial — Lesson

## Problem

The production critic model (`qwen3.6-27b`) needed validating against a
candidate (`gemma-4-26b-a4b-it-mlx`) before either could be trusted as the
authoring pipeline's QA gate. The trial's actual outcome diverged sharply
from its premise: the incumbent turned out to be completely non-functional
in this environment, not just a quality baseline to beat.

## What worked

**Diagnosing the qwen3.6-27b failure down to the actual request field,
not stopping at the first plausible explanation.** The existing error
message in `lm_client.py` blamed `max_tokens` exhaustion by
`reasoning_content`. The failure signature (`finish_reason='stop'`, ~131
tokens generated against an 8192 budget) didn't match that theory —
`finish_reason='length'` would. Isolating the call outside the harness
with direct `curl` requests, varying one field at a time
(`response_format` type, `strict` value, quant backend), found the real
cause: `response_format: json_schema` returns empty content on this LM
Studio version, on two independent quant backends, while the same schema
spelled out in prompt text under `response_format: {"type": "text"}`
works. Stopping at the existing (wrong) error message would have sent
whoever hit this next toward raising `max_tokens` — a fix that does
nothing for this failure.

**Naming the evidence gap instead of overstating the comparison.**
qwen3.6-27b produced zero usable verdicts, so the trial couldn't run the
three-way, adopt-vs-incumbent comparison the design called for. Rather
than quietly substituting a two-way Gemma-vs-Gemma comparison and letting
the write-up imply it answered the original question, the write-up and QA
review both state the narrower scope explicitly (AC2/AC3 marked
"PARTIALLY MET, and the write-up says so") — the adopt recommendation
still holds, but on its own actual evidence, not inflated evidence.

**Independently re-deriving every numeric claim from raw data during QA
rather than re-reading the prose.** Verdict agreement (11/15), latency
ratio (0.94x), and the mutated-case defect-catch table were each
recomputed from the `aggregate-*.json` files and `.defect.md` labels using
`scripts/gemma_critic_trial_diff.py`, independent of the write-up's own
numbers. All matched exactly — worth doing even when a result looks
clean, since the check is cheap relative to what a silently-wrong number
in a model-adoption decision would cost.

## What didn't work / had to be corrected

**`agentalloy phase set` reads a different cursor file than `agentalloy
task start` writes.** `task start <slug>` persists the active work-item
slug to a session-scoped file (`.agentalloy/cursor.<session_key>`, via
`_write_cursor_atomic` in `task.py`), but the exit-gate's `lessons_recorded`
and related predicates in `predicates.py` read the plain, unscoped
`.agentalloy/cursor` file directly — bypassing session scoping entirely.
Running `task start gemma-4-critic-model-trial` alone left the plain
cursor file pointed at a stale, unrelated work item, so `phase set ship`
kept resolving the wrong slug's artifacts. Fixed by writing the plain
cursor file directly (`printf '<slug>' > .agentalloy/cursor`). Worth a
real fix in the CLI (either `task start` should write both files, or the
gate predicates should read the session-scoped file when a session key is
available) rather than requiring this manual workaround every time.

**QA report section headings need to match the gate's expected names
exactly, prefix included.** The `qa` phase's exit gate checks
`artifact_contains` for section headings `Checks` and `Review` across
*every* file matching `docs/qa/*.md`, and `_section_present`'s
"word-boundary, trailing qualifier" matching only tolerates a suffix after
the section name (`## Checks (AC3)` still matches `Checks`) — a prefix
(`## QA Checks`) does not. Written the QA report's sections as `## QA
Checks` / `## QA Review` / `## QA Verdict` initially, matching this task's
own naming preference rather than the bare `## Checks` / `## Review` /
`## Verdict` convention every other file in `docs/qa/` actually uses, and
the phase-advance gate failed silently (no advisory text distinguishing
this from any other reason) until the headings were renamed to match.

## Decisions worth keeping

- When an error message's stated cause doesn't match the actual failure
  signature (wrong finish_reason, wrong token count), trust the signature
  over the message and isolate the call outside the harness one field at
  a time rather than patching around the documented-but-wrong cause.
- State a narrowed evidence base plainly in both the write-up and the QA
  review rather than letting scope quietly shrink between what was
  planned and what was actually delivered.
- Re-derive quantitative claims from source data during QA even when nothing
  looks suspicious — the check is cheap and this is exactly the kind of
  finding that stays invisible until independently recomputed.
- Match a generated artifact's section headings to the *exact* literal
  convention already established by sibling files in the same directory,
  not just to what reads well for this specific task — a phase gate that
  scans by heading text has no tolerance for a differently-styled but
  semantically-equivalent heading.
