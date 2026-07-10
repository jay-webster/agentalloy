# automation-integrator-intake — Tasks

## Tasks

1. **`automation/integrator.py` — `slugify` + `render_draft`.** Pure
   functions per approach.md §1-2, no I/O, no dependency on `store.py`. No
   dependency on other tasks. Satisfies AC3, AC4.

2. **`automation/store.py` — `integrate()` + storage.** Extend
   `_NEW_COLUMNS` with `integrated_at`/`integration_slug`; add
   `IntegrationResult` dataclass, `NotAcceptedError` exception, and
   `CandidateStore.integrate(message_id) -> IntegrationResult` per
   approach.md §3 (missing-row raise, non-accept raise, idempotent
   no-file-write short-circuit, otherwise slugify+render+write+update).
   Depends on Task 1. Satisfies AC1, AC2, AC5.

3. **`automation/cli.py` — `ingest integrate`.** New subcommand wired to
   Task 2, per approach.md §4. Depends on Task 2. Satisfies AC1, AC2, AC5
   at the CLI level.

4. **Live proof.** Construct a synthetic `accept` candidate via the real
   CLI (`add` → `evaluate --verdict accept` → `integrate`), inspect the
   generated draft file's real contents, run `integrate` a second time to
   confirm the idempotency guarantee holds for real (not just unit-tested),
   then delete the test candidate row and draft file. Depends on Tasks 1-3.
   Satisfies AC7.
