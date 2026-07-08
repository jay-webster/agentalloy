# Compound Engineering ↔ AgentAlloy Bridge — Design

> Runtime home: `docs/design/compound-engineering-bridge/approach.md` (git-ignored).
> This is the committed copy. Acceptance lives in
> `docs/spec/compound-engineering-bridge.md` (`## Acceptance Criteria`, AC 1–8)
> and is not reopened here.

## Approach

The feature is two subsystems joined only by a shared file convention
(`docs/solutions/<slug>.md`). They ship independently and touch disjoint code, so
the design keeps them decoupled: Piece 1 is a **gate + prose** change on the ship
workflow skill; Piece 2 is a **new CLI subcommand** that reuses the pack rail.
Nothing here touches `code_index/`, `retrieval/`, or `api/` (AC 6) — the
read-path is inherited.

Below, each of the five decisions the spec deferred is committed with its
rationale and the alternative rejected.

### D1 — Codify-gate predicate: a new slug-scoped `lessons_recorded`

**Decision.** Add one new deterministic predicate,
`lessons_recorded`, to `signals/predicates.py`, registered in the `PREDICATES`
dict. It resolves the **active task slug** from the ship work-item contract
(the newest `.agentalloy/contracts/ship/*.md`, matching how the phase already
tracks its work-item) and returns `MET` iff `docs/solutions/<slug>.md` exists,
`NOT_MET` otherwise, `UNKNOWN` on an unreadable/absent contract. It mirrors
`eval_approval_recorded` (predicates.py) for the slug-derivation pattern and
reuses the shared `_glob_files` helper.

**Why not reuse `artifact_exists`?** Ruled out by AC 2: `artifact_exists:
docs/solutions/*.md` is `MET` on *any* match, so the first lesson ever written
satisfies it forever — the stale-file no-op the spec calls out.

**Why not reuse `artifact_newer_than`?** It would work
(`path=docs/solutions/*.md` newer than a `docs/ship/*.md` marker) but it is
**write-order-fragile**: if the agent writes the lesson *before* the ship record
in the same phase, `max(solutions_mtime) < max(ship_mtime)` and the gate falsely
reports `NOT_MET`. A slug-scoped existence check is order-independent and
unambiguous, which is worth ~15 lines of new predicate. The predicate is
DB-free (read straight from disk), so it needs no re-embed and takes effect the
moment the wheel carries it.

**Build-time verification required:** the slug the ship phase considers "active"
must be pinned to a single, unambiguous source. If multiple ship contracts can
coexist, resolve by the same rule the phase's own work-item cursor uses, not
"newest mtime" as a guess. Confirm against `skill_loader`/`contracts.latest_contract`
before coding.

### D2 — Gate the ship phase's own close-out edge

**Decision.** Append the `lessons_recorded` leaf to
`sdd-deliver-and-ship.yaml`'s `exit_gates.all_of` (alongside the existing
`artifact_exists docs/ship/*.md` and `artifact_contains …[Summary, Rollback]`),
so the lesson is the **last** thing a task produces — matching compound
engineering, where the compound step ends the run. Ship is terminal; its only
transition out is the user-initiated reset to `intake`, and that transition is
what the leaf gates.

**Why not gate `qa → ship`?** Codifying before the change is even shipped is
premature — the delivery record (`docs/ship/<slug>.md`, written in ship §3) and
any late lesson from the act of shipping wouldn't be captured yet. Ship
close-out is the natural terminal seam and sits right next to §3 "Record the
delivery," where the prose change lands.

**Build-time verification required:** confirm the ship→intake reset actually
evaluates ship's `exit_gates` through `_forward_gate_blocks` /
`decide_transition`. Grounding showed the forward-gate machinery evaluates the
current phase's gates, but a *reset* (backward jump to the start) may be treated
specially. If the reset bypasses exit-gate evaluation, fall back to gating the
`qa → ship` edge instead — the predicate is identical; only the host pack YAML
(`sdd-verify-and-review.yaml`) changes. This is the one place the design has a
branch; resolve it with a spike before task 02.

### D3 — `--force` bypasses codify (no carve-out)

**Decision.** `lessons_recorded` is an ordinary forward-gate completeness leaf.
`agentalloy phase set --force` bypasses it, as it does the other completeness
leaves — an intentional, logged escape hatch. We do **not** add an unconditional
carve-out like the #10 approval gate's `_approval_gate_blocks`.

**Why.** Proportionality. The approval gate guards a *human sign-off* that
`--force` must not silently skip; codify is a completeness obligation, not a
trust boundary. No AC requires `--force` survival. Adding a carve-out would
over-constrain the escape hatch users rely on when they legitimately need to
move on.

### D4 — Promotion is a new first-class CLI subcommand

**Decision.** Add `agentalloy lessons promote <slug>` (module
`src/agentalloy/install/subcommands/lessons.py`), with a helper generator module
that turns `docs/solutions/<slug>.md` into a domain-skill pack under
`.agentalloy/custom-skills/<slug>-lesson/`, then installs it by calling the
**existing** `install_local_pack` code path (strict mode, dedup on). The
lesson→fragment mapping is the spec's table: approach→`execution`,
verification→`verification`, decision/what-didn't-work→`rationale`; the lesson's
module/problem tags → `domain_tags` (clamped to the domain tier's soft ceiling).

**Why not the interactive `add-skill` lane?** That lane is an agent-driven,
per-skill human-authoring session gated by `agentalloy approve add-skill`.
Promotion is a *batch transform* of an existing artifact — it should be
scriptable and composable (CI, a post-ship hook), which a CLI subcommand is and
the interactive lane is not. The subcommand still reuses the lane's install rail
and its custom-skills location, so nothing is reimplemented.

### D5 — Duplicate handling: pre-ingest similarity probe

**Decision.** Before installing, the subcommand **embeds the candidate fragments
and runs the dedup classifier against the corpus** (`dedup_gate.classify_hit`,
hard ≥ 0.92 / soft ≥ 0.80). On a hard hit it **refuses the promotion** and names
the near-duplicate skill; on a soft hit it warns and proceeds; `--allow-duplicates`
downgrades a hard hit to a warning. Only after the probe passes does it call the
install rail.

**Why a pre-ingest probe rather than post-`EXIT_DEDUP` rollback?** The spec's
fact-check established that `install-pack` writes the skill rows and vectors
*before* the dedup pass runs and never rolls back — `EXIT_DEDUP` is only an exit
code. Prevention beats cleanup: probing first means a hard duplicate is never
written, so AC 5's "not left served in the corpus" holds without inventing an
uninstall path (which doesn't exist today). The probe reuses the same embed
model and classifier the rail uses, so its verdict matches what the rail would
have reported.

## Non-goals carried from spec

No change to `code_index/`, `retrieval/`, `api/`, or the pre-seeded corpus; no
automatic promotion; injection of a promoted skill is inherited from the
existing install→corpus→signal rail and not re-implemented or re-tested here
(AC 6). See `docs/spec/compound-engineering-bridge.md` `## Out of Scope`.
