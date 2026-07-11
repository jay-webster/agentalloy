# Automation Risk Classifier — Spec

> **Scope in a sentence.** A deterministic function that classifies a set
> of changed file paths as `low` or `high` risk — the gate tiered autonomy
> (Jay's explicit direction) needs before any auto-merge decision can be
> made, built and tested independently of the GitHub-side CI verification
> it will eventually gate.

> **Location note.** At runtime the SDD spec phase writes the spec to
> `docs/spec/automation-risk-classifier.md`, git-ignored. This file is the
> committed, reviewable copy.

## Context

Jay's stated goal is a fully autonomous coding environment — auto-merge
and auto-deploy. Two real findings while scoping toward that: (1) "deploy"
is already solved — `release-cut.yml` on this repo automatically cuts a
GitHub release whenever a version bump lands in a merged PR on `main` with
green CI; (2) `main` currently has no branch protection, `allow_auto_merge`
is off, and **GitHub Actions has never run on this fork** (standard
fork behavior — disabled until manually enabled once). Auto-merge is
meaningless without real, enforced CI checks behind it, so wiring the
actual `gh pr merge --auto` mechanism is blocked on Jay confirming Actions
is live and a real PR shows real passing checks.

This slice does not wait on that. Jay's chosen safety net — **tiered
autonomy by risk** — needs a classification function regardless of what
gates the merge itself (GitHub-side CI, or something else). That function
is pure logic over a list of changed file paths, fully buildable and
testable right now, independent of GitHub's CI state.

## Assumptions (correct these before design)

- **Classification is by file path, not by content inspection or intent.**
  A change is `low` risk if and only if every changed path matches an
  explicit allowlist of low-blast-radius locations (skill/corpus content,
  documentation). Any path outside the allowlist makes the whole change
  `high` risk — one risky file is enough to disqualify an otherwise
  content-only change from auto-merge eligibility.
- **The allowlist starts narrow and explicit**, matching tonight's dry-run
  precedent (`src/agentalloy/_packs/**` — proven tonight as a real,
  low-blast-radius change category — and `docs/**`). Expanding it later is
  a deliberate, reviewable decision, not something this slice tries to
  anticipate.
- **This classifier does not itself decide to merge anything.** It answers
  "is this low-risk," full stop — wiring that answer into an actual
  auto-merge action is later work, explicitly gated on Jay confirming CI
  actually runs (see Context).
- **Never trust declared scope alone.** A build contract's `scope.touches`
  field is author-declared during design and can be wrong or incomplete
  (as tonight's dry run's own build contracts were, self-reported before
  the code existed). This classifier must be run against the *real* diff
  (actual changed file paths from git), never the declared scope alone.

## What

**Classifier function.** `automation/risk_classifier.py`:
`classify(changed_paths: list[str]) -> Literal["low", "high"]` — `low` iff
every path in `changed_paths` matches at least one entry in a small,
explicit allowlist of path prefixes/globs; `high` otherwise, including for
an empty allowlist match on any single path. Also exposes the allowlist
itself as a named, importable constant (`LOW_RISK_PATH_PREFIXES` or
similar) so it can be inspected/tested directly, not just through the
function's behavior.

**No merge/deploy wiring in this slice.** See Out of Scope.

## Acceptance Criteria

1. **All-allowlisted paths classify low.** A change touching only
   `src/agentalloy/_packs/core/some-skill.yaml` and
   `docs/some-doc.md` classifies `low`. Verifiable by a unit test.
2. **Any single disallowed path makes the whole change high**, even when
   every other path is allowlisted. A change touching
   `src/agentalloy/_packs/core/some-skill.yaml` AND
   `automation/store.py` classifies `high`. Verifiable by a unit test.
3. **A change touching only clearly risky paths classifies high.** E.g.
   `src/agentalloy/retrieval/hybrid.py` alone classifies `high`.
   Verifiable by a unit test.
4. **Empty input is handled explicitly**, not accidentally passing as
   `low` by vacuous truth. `classify([])` — design decides the correct
   answer (see Design surface) but it must be an explicit decision, not
   whatever the "all() on an empty list" default happens to produce
   unexamined.
5. **No product code touched, no new dependency, no LLM call.** Same bar
   as every prior slice — zero diff under `src/agentalloy/`; the
   classifier is pure path-matching, no external call of any kind.
6. **Live proof against a real diff.** Run the classifier against the real
   changed-file list from tonight's `agentalloy-guardrail-mcp-injection`
   dry-run branch (`src/agentalloy/_packs/core/mcp-tool-trust-guardrail.yaml`,
   `src/agentalloy/_packs/core/pack.yaml`) and confirm it classifies `low`
   — this is real, already-shipped-and-reviewed evidence of what a genuine
   low-risk change looks like, not a synthetic fixture.

## Out of Scope

- **Wiring the classifier into an actual merge decision** (`gh pr merge
  --auto` or equivalent). Explicitly deferred — blocked on Jay confirming
  GitHub Actions actually runs and a real PR shows real passing checks.
- **Expanding the allowlist** beyond `src/agentalloy/_packs/**` and
  `docs/**` — a deliberate future decision, not attempted here.
- **Any automated SDD execution.** This slice classifies risk for a diff
  that already exists; it does not generate one.
- **Any cloud or paid-LLM call.**

## Design surface (hand-off to the design phase)

- **Empty-input behavior** — should `classify([])` be `low` (nothing risky
  touched) or `high` (fail closed on no evidence)? Given this gates
  autonomous action, "fail closed" (treat unknown/empty as `high`) is the
  safer default absent a concrete reason otherwise — design confirms this
  explicitly rather than leaving it to `all()`'s vacuous-truth default.
- **Path matching mechanism** — `str.startswith()` on prefixes vs.
  `fnmatch`/`pathlib.Path.match()` glob patterns. Given the allowlist is
  currently just two directory prefixes, the simplest correct mechanism
  wins; don't over-engineer for glob patterns not yet needed.
