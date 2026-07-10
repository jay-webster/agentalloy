# automation-email-ingestion — Design

## Approach

### 1. Store: stdlib `sqlite3`, not DuckDB

The rest of this repo standardizes on DuckDB for the skill corpus and code
index — both are analytical, multi-table, query-heavy stores serving a
retrieval engine. This store is neither: it's a single append-mostly log
table serving one writer (the ingestion routine) and one reader (the
evaluator, later). `sqlite3` is stdlib (zero new dependency), file-based
(trivially git-ignorable), and its locking model needs no more sophistication
than this use case requires. Matching the DuckDB convention here would be
extra surface for no benefit — `automation/` is deliberately a separate
package from `src/agentalloy/`, so it isn't bound to the product's storage
convention.

**Decision.** `automation/store.py`: `CandidateStore` wrapping a single
`sqlite3.Connection` against `.automation/candidates.db`, one table:

```sql
CREATE TABLE IF NOT EXISTS candidates (
    message_id  TEXT PRIMARY KEY,
    thread_id   TEXT NOT NULL,
    source      TEXT NOT NULL,
    subject     TEXT NOT NULL,
    received_at TEXT NOT NULL,
    snippet     TEXT NOT NULL,
    status      TEXT NOT NULL DEFAULT 'new',
    ingested_at TEXT NOT NULL
);
```

`message_id PRIMARY KEY` gives idempotency (AC1) for free via `INSERT ...
ON CONFLICT(message_id) DO NOTHING` — no separate existence check needed.
`status` defaults to `'new'` (AC2) at the schema level, not just in
application code, so it can't drift.

### 2. Runtime layout mirrors the existing `.agentalloy/` convention

**Decision.** `.automation/candidates.db` (git-ignored) for the database,
`automation/config/sources.yaml` (git-ignored, real, personal to Jay) for the
allowlist, `automation/config/sources.example.yaml` (tracked) as the
template new users/future-Jay copy from. This is the same tracked-example
vs. git-ignored-real split the product already uses for `.env`
(`write-env.py`), so it's a familiar shape rather than a new convention.

### 3. Config loader: `pyyaml` (already a dependency), fails loud and specific

**Decision.** `automation/config.py`: `load_sources(path=None) ->
SourceAllowlist` (`frozenset[str]` of sender addresses/domains). Missing
`sources.yaml` raises a `SourcesConfigMissing` error whose message names the
example file to copy — not a silent empty allowlist (an empty allowlist
would make the ingestion routine's Gmail query, built by joining the
allowlist, either match nothing or degenerate to matching everything,
neither of which fails safely). Malformed YAML (not a list of strings)
raises with the offending value, not a generic parse error.

### 4. CLI: `argparse`, matching `agentalloy`'s own entry point style

**Decision.** `automation/cli.py`, run as `python -m automation.cli`.
Subcommands under `ingest`: `add` (positional/flags for each candidate
field, calls `CandidateStore.add`), `list` (`--status` filter, prints one
line per row), `mark` (`message_id` + new `status`, reports whether a row
existed). No new CLI dependency — `argparse` is stdlib and is what
`agentalloy.install.__main__` already uses, so there's no new pattern for
future-Jay to learn.

### 5. The routine is a markdown document, not code

**Decision.** `automation/routines/scan-newsletters.md` is instructions, not
a script — because the actor executing it is an agent with Gmail MCP access
(this session tonight; a scheduled Claude Code agent later), not a
standalone process. It specifies: build a Gmail search query from
`automation/config/sources.yaml`'s addresses/domains (`OR`-joined `from:`
clauses), call `search_threads`, for each matching thread extract
`message_id`/`thread_id`/sender/subject/received-date/snippet, and record
each via `python -m automation.cli ingest add`. Keeping this as an explicit,
literal routine (rather than "an agent figures out how to scan email") is
what makes the ingestion step auditable and repeatable across runs and
across whichever agent executes it — the same "deterministic over guessed"
preference the spec's Assumptions section states, applied to a step that
necessarily involves agent judgment (reading email content) by pinning down
everything that *doesn't* need judgment.

### 6. `pyproject.toml` scope additions — additive only

**Decision.** Add `"automation"` to `tool.ruff.src` and `tool.pyright.include`
lists, and add `"."` to `tool.pytest.ini_options.pythonpath` (alongside the
existing `"src"`) so `tests/automation/` can `import automation...`
regardless of invocation cwd. No existing entries in any of these lists are
removed or changed — verifies AC6's "no behavior change to the existing
`agentalloy` package" by inspection (diff is additive lines only).

## Non-goals carried from spec

No headless/unattended Gmail client. No evaluation logic — `mark` moves a
candidate to `evaluated`/`accepted`/`rejected` but nothing in this slice
decides which. No Discord wiring. No LLM call anywhere in `store.py`,
`config.py`, or `cli.py` (the routine itself is agent-executed by
definition, but ships no LLM-calling *code*).
