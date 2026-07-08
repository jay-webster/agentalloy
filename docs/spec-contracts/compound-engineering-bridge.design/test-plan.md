# Compound Engineering ↔ AgentAlloy Bridge — Test Plan

> Runtime home: `docs/design/compound-engineering-bridge/test-plan.md` (git-ignored).
> Committed copy. Cases are written as behaviors (input → expected), each closing
> a spec acceptance criterion. Build turns these red first, then adds edges.

## Test Cases

- **TC1 — codify gate blocks close-out (AC 1).** Given a wired repo at `ship`
  with the ship contract for `<slug>` and **no** `docs/solutions/<slug>.md`,
  evaluating ship's `exit_gates` returns `NOT_MET`; after writing
  `docs/solutions/<slug>.md`, it returns `MET`. *(predicate unit + phase-gate.)*

- **TC2 — stale lessons file does not satisfy the gate (AC 2).** Given the active
  slug is `<slug>` but only `docs/solutions/<other>.md` exists (a prior task's
  lesson), `eval_lessons_recorded` returns `NOT_MET`. This is the explicit guard
  against the `artifact_exists: *.md` no-op.

- **TC3 — prose/gate self-consistency (AC 3).** Loading the shipped
  `sdd-deliver-and-ship` skill produces **no** invariant-violation warning, and
  its `raw_prose` contains the literal `docs/solutions/` token. *(A prose-invariant
  test over `derive_invariants` + `check_prose`.)*

- **TC4 — generator emits a strict-valid pack (AC 4).** Given a well-formed
  `docs/solutions/<slug>.md`, the generator's output directory passes
  `agentalloy validate-pack` in strict mode — `execution` + `verification` +
  `rationale` fragments present, a valid production category, `domain_tags` within
  the domain soft ceiling, `raw_prose` a contiguous concatenation of fragments.

- **TC5 — duplicate lesson is refused pre-ingest (AC 5).** Promoting a lesson
  whose fragments are ≥ 0.92 cosine to an existing corpus skill: the probe reports
  the near-duplicate and the command refuses (non-zero), and afterward the corpus
  contains **no** new skill row/vector for it. With `--allow-duplicates`, it
  proceeds and warns. *(Uses a seeded fixture skill for the collision.)*

- **TC6 — read-path untouched and still retrieving (AC 6).** A guard test asserts
  the diff touches no file under `src/agentalloy/code_index/`,
  `src/agentalloy/retrieval/`, or `src/agentalloy/api/`; and after indexing a
  repo with a `docs/solutions/x.md`, `agentalloy code search` returns that chunk
  with no code change.

- **TC7 — opt-out parity (AC 7).** With `lifecycle-mode off`, `evaluate_signal`
  returns full passthrough and the ship gate/codify prompt never compose; with
  `flow free`, workflow steering (including the codify gate) is paused. Neither
  fires.

- **TC8 — migration note present (AC 8).** The shipped `sdd-deliver-and-ship`
  `change_summary` and the spec's Piece 1 both state that a pre-existing enabled
  profile override lacking the `docs/solutions/` token is dropped at runtime until
  its author adds the token. *(A doc/string-presence assertion.)*

**Coverage map:** AC1→TC1, AC2→TC2, AC3→TC3, AC4→TC4, AC5→TC5, AC6→TC6,
AC7→TC7, AC8→TC8. Every AC has at least one case; TC1/TC2 and TC5 carry the two
correctness risks the spec's fact-check surfaced (stale-file trap; dedup is a
signal not a prevention).
