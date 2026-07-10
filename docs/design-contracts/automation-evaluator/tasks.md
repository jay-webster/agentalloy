# automation-evaluator — Tasks

## Tasks

1. **`automation/store.py` — migration + `evaluate()`.** Add
   `_NEW_COLUMNS`, `_ensure_columns`, `VALID_VERDICTS`, and
   `CandidateStore.evaluate(message_id, verdict, rationale) -> bool` per
   approach.md §1-3. Extend `Candidate` dataclass with `verdict:
   str | None = None`, `rationale: str | None = None`,
   `evaluated_at: str | None = None`, and update `list()`'s row-to-dataclass
   mapping to include them. No dependency on other tasks. Satisfies AC1,
   AC2, AC3, AC4, AC5.

2. **`automation/cli.py` — `ingest evaluate`.** New subcommand per
   approach.md §4, wired to Task 1's `evaluate()`. Extend `_cmd_list`'s
   output per approach.md §5. Depends on Task 1. Satisfies AC2-AC6 at the
   CLI level (on top of Task 1's store-level coverage).

3. **`automation/routines/evaluate-candidate.md`.** The routine per
   approach.md §6: for each `status="new"` candidate, best-effort fetch full
   body, assess against the spec's two lenses (feature fit,
   local-model-replacement fit), record via Task 2's CLI. Depends on Task 2
   existing so it can reference the real CLI shape. No code, no tests of its
   own — verified by Task 4.

4. **Live proof run.** Follow the Task 3 routine by hand against slice 1's
   31 real ingested candidates. Depends on Tasks 1-3. Satisfies AC8. Not a
   code task — a session transcript of real commands against real data,
   same shape as slice 1's task 6.
