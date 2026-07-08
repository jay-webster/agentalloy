# Compound Engineering ↔ AgentAlloy Bridge — Task Plan

> Runtime home: `docs/design/compound-engineering-bridge/tasks.md` (git-ignored).
> Committed copy. Each task is one dominant tech surface and becomes one build
> contract (`../compound-engineering-bridge.build/NN-*.md`, ≤ 2 `domain_tags`).

## Tasks

1. **Add the `lessons_recorded` predicate** *(surface: signal predicates)* —
   Implement `eval_lessons_recorded` in `signals/predicates.py`, register it in
   `PREDICATES`, resolving the active slug from the ship work-item contract and
   returning `MET`/`NOT_MET`/`UNKNOWN` against `docs/solutions/<slug>.md`. Mirror
   `eval_approval_recorded`. Includes the D1 slug-resolution spike.
   Closes **AC 1**, **AC 2**. Build contract `01`.

2. **Wire the ship gate + codify prose** *(surface: SDD workflow-skill YAML)* —
   In `sdd-deliver-and-ship.yaml`: append the `lessons_recorded` leaf to
   `exit_gates.all_of`; add a codify instruction to the "Checkpoint first"
   paragraph and §3 "Record the delivery" so `raw_prose` literally contains the
   `docs/solutions/` token derive_invariants now requires; update `change_summary`
   with the override-migration note. Precede with the D2 spike confirming the
   reset edge evaluates ship's gates (else host the leaf on
   `sdd-verify-and-review.yaml`). Closes **AC 3**, **AC 8**; contributes **AC 1**.
   Build contract `02`.

3. **Lesson→domain-skill pack generator** *(surface: skill-pack authoring)* —
   A module that parses `docs/solutions/<slug>.md` into a valid domain-skill pack
   (`pack.yaml` + skill YAML with `execution` + `verification` + `rationale`
   fragments, a production category, `domain_tags` within the soft ceiling,
   `raw_prose` = the ordered fragment concatenation) under
   `.agentalloy/custom-skills/<slug>-lesson/`. Closes **AC 4**. Build contract `03`.

4. **`agentalloy lessons promote` CLI + pre-ingest dedup probe** *(surface: CLI
   subcommand)* — New `install/subcommands/lessons.py` registering `lessons
   promote <slug>`: run the generator, embed candidate fragments, run
   `dedup_gate.classify_hit`, refuse on a hard hit (name the duplicate) unless
   `--allow-duplicates`, then call `install_local_pack`. Closes **AC 5**.
   Build contract `04`.

5. **No-regression + opt-out guards and docs** *(surface: tests & docs)* —
   Tests asserting no diff under `code_index/`/`retrieval/`/`api/` and that
   `docs/solutions/*.md` stays retrievable via `agentalloy code search`; a test
   that the codify gate and prompt stay inert under `lifecycle-mode off` /
   `flow free`; a README note framing this as the first slice of the Knowledge
   module. Closes **AC 6**, **AC 7**. Build contract `05`.

**Order & dependencies.** 1 → 2 (the gate leaf needs the predicate; do the D1/D2
spikes first). 3 → 4 (the CLI drives the generator). 5 is verification/docs, last.
Pieces 1 (tasks 1–2) and 2 (tasks 3–4) are independent and can proceed in
parallel after their spikes; task 5 closes out both.
