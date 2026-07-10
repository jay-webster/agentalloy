# automation-email-ingestion — Tasks

## Tasks

1. **`automation/store.py` — `CandidateStore`.** SQLite-backed, schema per
   approach.md Section 1, opened against `.automation/candidates.db`
   (directory created on demand). Methods: `add(candidate) -> bool` (returns
   whether a new row was inserted, `False` on idempotent no-op),
   `list(status=None) -> list[Candidate]`, `mark(message_id, status) -> bool`
   (returns whether a row existed to update). `Candidate` is a frozen
   dataclass mirroring the table columns. No dependency on other tasks.
   Satisfies AC1, AC2, AC3, AC4.

2. **`automation/config.py` — allowlist loader.** `load_sources(path=None) ->
   SourceAllowlist`, `SourcesConfigMissing` exception naming the example
   file. `automation/config/sources.example.yaml` tracked with 2-3 realistic
   placeholder entries and a comment explaining the copy step. No dependency
   on other tasks. Satisfies AC5.

3. **`automation/cli.py` — `ingest add|list|mark`.** `argparse`-based,
   wires Task 1's store directly (no indirection layer — this is a small
   enough surface that one more abstraction would be premature). `list`
   prints a compact one-line-per-row table to stdout. Depends on Task 1.
   Satisfies AC1–AC4 at the CLI level (on top of Task 1's store-level
   coverage) and is what the routine (Task 4) and the live proof (Task 5)
   actually invoke.

4. **`automation/routines/scan-newsletters.md`.** The documented routine
   per approach.md Section 5. Depends on Tasks 2 and 3 existing (it
   references the config path and the exact CLI invocation). No code, no
   tests of its own — verified by actually following it in Task 5.

5. **`pyproject.toml` scope additions.** Add `automation` to
   `tool.ruff.src`, `tool.pyright.include`, and `.` to
   `tool.pytest.ini_options.pythonpath`. Add `.automation/` and
   `automation/config/sources.yaml` to `.gitignore`. No dependency on other
   tasks; needed before Tasks 1-3's tests can run cleanly under the repo's
   standard `pytest`/`ruff`/`pyright` invocations. Satisfies AC6.

6. **Live proof run.** Once Gmail is reconnected: create a real
   `automation/config/sources.yaml` from the example (Jay's actual
   newsletter senders), follow the Task 4 routine by hand in this session —
   run the Gmail search, extract fields, call `ingest add` for each real
   match — then `ingest list` and show the output. Depends on Tasks 1-4.
   Satisfies AC8. Not a code task; no diff, just a session transcript of
   real commands against real data.
