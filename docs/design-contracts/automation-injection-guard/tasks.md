# automation-injection-guard — Tasks

## Tasks

1. **`automation/injection_guard.py` — pattern screen.** `_PATTERNS` +
   `screen(text) -> list[str]` per approach.md §1. No dependency on other
   tasks. Satisfies AC1.

2. **`automation/store.py` — flag storage + `add()` wiring + `evaluate()`
   enforcement.** Extend `_NEW_COLUMNS` with `flagged`/`flag_reasons`;
   `add()` calls Task 1's `screen()` against `subject + snippet` and stores
   the result; `Candidate` dataclass gains `flagged: bool = False`,
   `flag_reasons: str = ""`; `evaluate()` raises the new
   `FlaggedCandidateError` when `flagged` is true and `verdict == "accept"`,
   per approach.md §2-3. Depends on Task 1. Satisfies AC3, AC4, AC5, AC6.

3. **`automation/cli.py` — surface the flag.** `_cmd_evaluate` catches
   `FlaggedCandidateError` and prints the clear refusal message per
   approach.md §4; `_cmd_list` prefixes flagged rows. Depends on Task 2.
   Satisfies AC7 at the CLI level.

4. **`automation/routines/evaluate-candidate.md` update.** Add the
   defense-in-depth instruction for full-body content per the spec's
   Assumptions, and note that `ingest list`'s `[FLAGGED]` marker means
   `accept` will be refused. Depends on Task 3 (references the real CLI
   behavior). No new tests — covered by Task 5's live proof.

5. **Live proof, both directions.** Re-screen all real candidates from
   slices 1-2 (AC2, real-data false-positive check) and run at least one
   deliberately crafted injection attempt through the real `add()` →
   `evaluate()` path (AC9, confirms the refusal is real, not just
   unit-tested). Depends on Tasks 1-4.
