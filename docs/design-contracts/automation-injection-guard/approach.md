# automation-injection-guard — Design

## Approach

### 1. Screening: a small pattern module, run at `add()` time

**Decision.** New file `automation/injection_guard.py`:

```python
_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("ignore-previous-instructions", re.compile(r"ignore (all |any )?(previous|prior|above) instructions", re.I)),
    ("disregard-above", re.compile(r"disregard (the )?(above|previous)", re.I)),
    ("new-instructions", re.compile(r"new instructions\s*:", re.I)),
    ("role-override", re.compile(r"you are now|act as if you|system (prompt|override)", re.I)),
    ("direct-agent-address", re.compile(r"\b(AI|agent|assistant)\s*,?\s*(you must|you should|please)\b", re.I)),
]

def screen(text: str) -> list[str]:
    return [name for name, pattern in _PATTERNS if pattern.search(text)]
```

Kept separate from `store.py` (not a store concern — it's a content-analysis
concern the store *calls*), matching this repo's existing convention of
small, single-purpose modules (`config.py` for config, `store.py` for
storage).

### 2. Storage: `flagged` + `flag_reasons`, computed at `add()`, same
migration pattern as slice 2

**Decision.** Extend `_NEW_COLUMNS` (already the mechanism slice 2 built)
with `flagged: "INTEGER"` (sqlite has no native boolean; `0`/`1`) and
`flag_reasons: "TEXT"`. `CandidateStore.add()` calls
`injection_guard.screen(candidate.subject + " " + candidate.snippet)`
before the `INSERT`, and stores the result — `flagged=1,
flag_reasons="ignore-previous-instructions, role-override"` when non-empty,
`flagged=0, flag_reasons=""` otherwise. Computing this at `add()` rather
than lazily at read time means the flag is a durable fact about the row
from the moment it's ingested, not something that could differ depending on
when/whether it's ever checked.

### 3. Enforcement: `evaluate()` raises, not silently downgrades

**Decision.** A flagged candidate requesting `"accept"` raises
`FlaggedCandidateError(message_id, flag_reasons)`, a new exception in
`store.py` (sibling to `ValueError` for bad verdicts — same "fail loud
before writing anything" shape). Chosen over silent downgrade because a
silent downgrade means the caller (agent, or future integrator) believes
its `accept` succeeded when it didn't — that's a worse failure mode than an
explicit, catchable error the CLI translates into a clear message. This
also means a flagged-but-*correctly*-worth-accepting candidate isn't lost —
it just requires an explicit, visible override path (not built in this
slice; see Out of Scope's "no auto-build on accept" — there's currently
nothing downstream that would act on an accept anyway, so there's no
urgency to build a bypass yet).

`reject` and `needs_review` requests proceed through `evaluate()`'s
existing path unchanged regardless of `flagged` — the gate is specific to
`accept`, per the spec's Assumptions (only `accept` carries downstream
risk).

### 4. CLI: catch `FlaggedCandidateError`, print a clear message; `list`
shows the flag

**Decision.** `_cmd_evaluate` wraps the `store.evaluate()` call; on
`FlaggedCandidateError`, print `"refused: {message_id} is flagged
({reasons}) — accept is blocked, use reject or needs_review"` to stderr and
exit 1 — same "clear message, no traceback, non-zero exit" shape as the
existing `mark`/`evaluate` missing-id path. `_cmd_list`'s row formatting
gets a `[FLAGGED: {reasons}]` prefix for flagged rows, before the existing
status/verdict fields, so it's the first thing visible per AC7 (agent sees
the signal before reading anything else about the row).

## Non-goals carried from spec

No screening of full fetched message bodies (routine-instruction layer
only, not code, for that surface). No integrator/auto-build. No ML
classifier — pattern list only. No retroactive rewrite of slices 1-2's
already-recorded verdicts.
