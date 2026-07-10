# Routine: evaluate-candidate

Followed by an agent with Gmail MCP access. Every step is literal except
step 3, which is a genuine judgment call — that's the point of this
routine.

## 1. Select candidates

Run `uv run python -m automation.cli ingest list --status new`. Each row is
one candidate to evaluate.

## 2. Get full content (best-effort)

For each candidate's `message_id`, try `get_message(message_id)` to read
the full email body — the stored `snippet` alone is often too thin to judge
fit. If the call fails for any reason (a manually-fed candidate with a
synthetic id, an API error, anything), don't stop the routine — fall back to
the stored `subject` + `snippet` and note in the eventual rationale that
only the snippet was available.

## 3. Assess against two lenses

Judge the content against exactly two questions:

- **Feature fit**: does this suggest a capability agentalloy doesn't have?
- **Local-model-replacement fit**: could this replace or improve
  agentalloy's own local embed model or reranker, independent of whether it
  suggests any new feature?

Decide:

- **Neither lens fires** → `reject`.
- **A lens fires clearly** → `accept`.
- **A lens fires but the fit is genuinely unclear**, or you can't tell
  without more context only Jay has → `needs_review`. Don't force a
  accept/reject call when the honest answer is "not sure" — that's what
  `needs_review` is for.

## 4. Record the verdict

```
uv run python -m automation.cli ingest evaluate "<message_id>" \
  --verdict <accept|reject|needs_review> \
  --rationale "<1-2 sentences naming which lens fired, or 'neither'>"
```

## 5. Report

After the batch, run `uv run python -m automation.cli ingest list --status
evaluated` and report the accept/reject/needs_review counts plus a one-line
summary of anything you marked `needs_review` (since that's the state that
will eventually need Jay's attention, once notification wiring exists).
