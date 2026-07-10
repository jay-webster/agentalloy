# automation-evaluator — Design

## Approach

### 1. Migration: check `PRAGMA table_info` before `ALTER TABLE ADD COLUMN`

Unlike DuckDB's `CREATE TABLE IF NOT EXISTS`, sqlite's `ALTER TABLE ...
ADD COLUMN` has no `IF NOT EXISTS` form and raises `OperationalError:
duplicate column name` on a second run. `CandidateStore.__init__` already
runs schema setup unconditionally on every open (matching slice 1's
existing `_SCHEMA_DDL` pattern) — the migration needs the same
run-every-time safety.

**Decision.** A small `_ensure_columns(conn)` helper: query
`PRAGMA table_info(candidates)`, collect existing column names, and only
run `ALTER TABLE candidates ADD COLUMN <name> <type>` for columns not
already present. Called once at the end of `CandidateStore.__init__`,
after `_SCHEMA_DDL`. This is checking state before acting, not
catching-and-ignoring the specific error — clearer failure mode if a
future column addition has a real bug (a different `OperationalError`
still surfaces).

```python
_NEW_COLUMNS = {
    "verdict": "TEXT",
    "rationale": "TEXT",
    "evaluated_at": "TEXT",
}
```

### 2. Verdict validation: application-level constant, not a `CHECK` constraint

A `CHECK` constraint's error (`sqlite3.IntegrityError: CHECK constraint
failed`) is generic — it doesn't say *which* check or what the valid values
are. AC5 wants a clear, actionable error. A small `VALID_VERDICTS =
frozenset({"accept", "reject", "needs_review"})` checked in
`CandidateStore.evaluate()` before touching the database, raising
`ValueError(f"verdict must be one of {sorted(VALID_VERDICTS)}, got
{verdict!r}")`, gives a precise message and fails before any I/O — matching
`config.py`'s existing "fail loud and specific" convention from slice 1.

### 3. `evaluate()` is a new `CandidateStore` method, not a variant of `mark()`

`mark()` (slice 1) only ever changes `status`. Evaluation changes four
columns together (`status`, `verdict`, `rationale`, `evaluated_at`) as one
atomic update — reusing `mark()` and bolting on optional params would blur
what it's for. A dedicated method keeps both simple:

```python
def evaluate(self, message_id: str, verdict: str, rationale: str) -> bool:
    if verdict not in VALID_VERDICTS:
        raise ValueError(...)
    # UPDATE candidates SET status='evaluated', verdict=?, rationale=?,
    #   evaluated_at=? WHERE message_id=?
    # returns cursor.rowcount > 0, same "found it or not" contract as mark()
```

`evaluated_at` is computed inside the method (current UTC time,
ISO 8601) — the caller (CLI, routine) doesn't have to supply it, removing
one place a bad timestamp could sneak in.

### 4. CLI: `ingest evaluate`, sibling to `add`/`list`/`mark`

Same `argparse` subparser pattern as slice 1. `--verdict` uses
`choices=sorted(VALID_VERDICTS)` so argparse itself rejects an invalid value
with a standard, clear CLI error — belt-and-suspenders with the store-level
`ValueError` (AC5 is satisfiable at either layer; both are covered so a
future direct-store caller is protected too, not just the CLI).

### 5. `list` output gains verdict/rationale, only when present

Extending the existing one-line-per-row format
(`message_id  status  source  subject`) unconditionally with two more
always-present-but-usually-empty columns would make slice 1's already-shipped
output noisier for `status="new"` rows (the common case pre-evaluation).

**Decision.** Append `verdict` and rationale only when the row has been
evaluated: `f"{msg}\t{status}\t{source}\t{subject}"` for un-evaluated rows
(byte-identical to slice 1's existing format — no regression), and
`f"{msg}\t{status}\t{source}\t{subject}\t[{verdict}] {rationale}"` for
evaluated ones.

### 6. Routine: fetch full body, fall back to the stored snippet

**Decision.** `automation/routines/evaluate-candidate.md` instructs: call
`get_message(message_id)` to get full content; if the call fails (a
manually-fed candidate with a synthetic id, or any other error), fall back
to the stored `subject` + `snippet` and note in the rationale that only the
snippet was available. Never hard-fail the routine on one candidate's fetch
error — move to the next one, consistent with slice 1's "one bad input
doesn't block the batch" philosophy (there it was an unresolvable symbol;
here it's an unfetchable body).

## Non-goals carried from spec

No auto-build on "accept" — this slice only records the verdict. No
notification wiring for `needs_review`. No new manual-entry CLI verb
(`ingest add` already covers it). No LLM call in `store.py` or `cli.py`.
