# MCP Tool Trust Guardrail — Spec

> **Scope in a sentence.** Add one new domain skill to agentalloy's corpus
> — a guardrail on treating MCP-connected tool output as untrusted input —
> sourced from a real, disclosed attack class this session's own automation
> pipeline is independently exposed to.

> **Location note.** At runtime the SDD spec phase writes the spec to
> `docs/spec/mcp-tool-trust-guardrail.md`, git-ignored. This file is the
> committed, reviewable copy.

## Context

This is the manual dry-run for the automation pipeline's deferred
"integrator" capability: proving that an `accept`-verdict candidate can
flow from the pipeline's draft intake artifact through a real SDD cycle to
a pushed (not merged) branch, before any of that gets automated. The
source candidate (`docs/spec-contracts/` from the automation-evaluator
slice, message_id `19ef0107615589f6`) is a real newsletter item disclosing
two host-level RCE attack classes against coding agents: "AutoJack"
(Microsoft-disclosed — a malicious web page reaching RCE through a
browsing agent via origin bypass, missing MCP auth, and unsafe shell
parameters) and "Agentjacking" (a crafted error injected into Sentry via a
public DSN; a coding agent executes the payload when it reads that error
through MCP — 85% success rate in real testing against 100+ organizations,
hitting Claude Code, Cursor, and Codex).

The structural point, attributed in the source article to Simon Willison's
"lethal trifecta" framing: any MCP-connected data source an agent both
reads *and* can act on — Sentry, Linear, GitHub issues, Jira, PagerDuty —
is the same category of risk, because the agent trusts whatever the tool
feeds it. agentalloy's own automation pipeline (`automation/`) is a live
instance of this pattern (it reads untrusted newsletter content via MCP)
and already shipped a real, structural mitigation for it tonight
(`automation/injection_guard.py` + `CandidateStore.evaluate()`'s refusal
of `accept` on flagged content) — a genuine, agentalloy-adjacent worked
example this skill can cite directly.

Note on the draft intake artifact that seeded this spec
(`automation/intake-drafts/one-fake-sentry-error-...-19ef0107.md`): its
"Original content" section only carried the store's thin `snippet` field
(the sender's brief preview text about an unrelated topic), not the actual
article body that justified the `accept` verdict — that content was fetched
live via Gmail during evaluation and never persisted. This spec is written
from this session's own retained knowledge of the real article, not the
draft's thin source material — a real gap in the integrator-intake design,
noted here for a future slice, not fixed as part of this dry run.

## Assumptions (correct these before design)

- **This lands in the `core` pack** (`src/agentalloy/_packs/core/`) —
  cross-cutting, stack-agnostic engineering discipline that applies
  regardless of language/framework, matching `incident-response` and
  `code-review-practices`' placement, not a language- or framework-specific
  pack. `core` is `always_install: true`.
- **Sourcing follows the pack's existing citation discipline** — every
  skill in `core` cites verified external sources with dates in
  `change_summary` (see `incident-response.yaml`'s SRE Book / PagerDuty
  citations). This skill cites the CTO Mode article itself plus the
  disclosed research it references (Microsoft's AutoJack disclosure, the
  Tenet-attributed Agentjacking testing, Simon Willison's lethal-trifecta
  framing) as accurately as this session can attribute them from having
  read the source.
- **The example fragment references agentalloy's own automation pipeline**
  as a real, concrete worked instance of the pattern — not a hypothetical.
- **This dry run stops at a pushed branch, not a PR.** Per this session's
  standing rule (ask before every push) and the explicit reasoning behind
  scoping tonight's SDD-execution conversation: a routine or an unattended
  process should never open a PR without a human deciding to at the time.
  This manual dry-run honors that same boundary even though a human (this
  session, interactively) is doing the work — proving the workflow stops
  at the right point, not just that it can produce a mergeable diff.

## What

**New skill**: `mcp-tool-trust-guardrail`, added to `src/agentalloy/_packs/core/`,
registered in `core/pack.yaml`. Content per the Assumptions above — the
lethal-trifecta framing, the "audit your agent's actual tool permissions"
actionable step from the source article, the "treat every MCP-connected
data source as the same untrusted surface" generalization, an anti-patterns
guardrail fragment, a worked example citing agentalloy's own
`injection_guard.py`, and a verification checklist.

**No other agentalloy code changes.** This is a pure content addition to
the skill corpus's source YAML — no changes to retrieval, composition,
signals, or any Python module.

## Acceptance Criteria

1. **New skill YAML is well-formed and matches the pack's existing
   convention.** All required top-level fields present (`skill_id`,
   `canonical_name`, `description`, `category`, `skill_class`,
   `domain_tags`, `phase_scope`, `category_scope`, `author`,
   `change_summary`, `raw_prose`, `fragments`); `raw_prose` and the
   concatenated `fragments` content match (same pattern as every existing
   `core` skill). Verifiable by direct inspection against
   `incident-response.yaml`'s structure.
2. **Fragment taxonomy satisfies strict-mode validation** — includes at
   least one each of `execution`, `verification`, and `rationale`
   (strict-mode `validate-pack`'s stated requirement), plus a `guardrail`
   fragment (the whole point of this skill) and an `example` fragment.
   Verifiable by running `agentalloy validate-pack` (or the equivalent
   installed-CLI command) against the `core` pack.
3. **`pack.yaml` is updated consistently** — new skill entry with correct
   `file` and `fragment_count` matching the actual fragment count in the
   new YAML file; pack version bumped per the existing versioning
   convention (`2.0.6` → next patch/minor, matching how prior skill
   additions bumped it). Verifiable by inspection.
4. **Sourcing is real, not fabricated.** `change_summary` names the actual
   source (the CTO Mode article, verifiably received message_id
   `19ef0107615589f6`) and the disclosed research it cites, with the
   verification date being this session's actual date. Verifiable by
   inspection — no invented citations.
5. **Cites agentalloy's own real mitigation as the example.** The
   `example` fragment references `automation/injection_guard.py` and
   `CandidateStore.evaluate()`'s structural refusal by name, describing
   what they actually do (verifiable against the real, already-shipped
   code, not a paraphrase that drifts from it).
6. **No product code touched beyond the pack YAML and its manifest.**
   Verifiable by `git diff --stat` showing only
   `src/agentalloy/_packs/core/mcp-tool-trust-guardrail.yaml` and
   `src/agentalloy/_packs/core/pack.yaml`.
7. **Work is pushed to a branch, never merged, never opened as a PR, as
   part of this dry run.** The branch exists on `origin` for Jay's own
   review and decision; this session does not open a PR against it.
   Verifiable by the session's own account of what git commands were run.

## Out of Scope

- **Opening a PR or merging this branch.** Explicitly the boundary this
  dry run is testing — see Assumptions.
- **Fixing the integrator-intake draft's thin "Original content" gap**
  found while starting this dry run — noted for a future slice, not solved
  here (would require deciding whether `evaluate()` should optionally
  persist more content, a real design question of its own).
- **Any other new skill, pack, or corpus change** beyond this one skill.
- **Automating this workflow into a routine.** This is explicitly the
  manual proof step that precedes any decision about automating SDD
  execution — see project memory on tonight's scoping conversation.

## Design surface (hand-off to the design phase)

- **Exact `domain_tags`** — should mirror the pack's existing tag style
  (short, hyphenated, e.g. `incident-response`'s
  `[incident-commander, mitigate-before-diagnose, ...]`) and cover the
  core concepts: MCP trust boundary, tool output as untrusted input,
  agent permission auditing.
- **`always_apply` value** — `incident-response` sets this `false` (only
  relevant during incidents); this skill's relevance is broader (any task
  touching MCP tool configuration or agent permission review) — design
  decides whether `false` (retrieved when relevant) or something narrower
  is right, based on how `phase_scope`/`category_scope` already scope
  retrieval.
