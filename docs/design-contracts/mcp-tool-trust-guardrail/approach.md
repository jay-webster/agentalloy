# mcp-tool-trust-guardrail — Design

## Approach

### 1. Fragment structure: 7 fragments, mirroring `incident-response.yaml`'s shape

**Decision.**

1. `rationale` — the lethal-trifecta framing: agents trust whatever their
   tools feed them; any MCP-connected source that's both read by and
   actionable to an agent is the same risk category.
2. `execution` — audit actual tool permissions (the source article's "go
   look this week" step): which shells, file systems, and credentials can
   the agent reach, not which it's assumed to be limited to.
3. `execution` — treat every MCP-connected data source as the same
   untrusted surface (Sentry, Linear, GitHub issues, Jira, PagerDuty —
   named in the source article as structurally identical: write-open
   ingestion, agent reads and acts).
4. `execution` — prefer a structural/code-level backstop over relying
   solely on prompting an agent not to follow embedded instructions,
   because a sufficiently crafted injection can defeat prompt-only
   defenses (the generalized lesson, stated before the concrete example
   fragment shows it applied for real).
5. `guardrail` — anti-patterns: trusting tool output as authoritative
   without review; granting default-all permissions; relying on "ignore
   untrusted instructions" as the *only* line of defense; treating a
   disclosed research finding as theoretical because it hasn't happened
   to you yet.
6. `example` — agentalloy's own automation pipeline
   (`automation/injection_guard.py`, `CandidateStore.evaluate()`) as a
   real, shipped instance: a deterministic pattern screen flags content
   that looks like it's addressing the agent with instructions, and
   `evaluate()` structurally refuses to write `verdict="accept"` for a
   flagged row — the code refuses, not just a routine instruction telling
   the agent to be careful.
7. `verification` — a checklist mirroring `incident-response`'s style.

Three separate `execution` fragments rather than one large one keeps each
fragment focused — matching this pack's existing practice of one concrete
idea per fragment.

### 2. Sourcing: cite what's actually known, precisely

**Decision.** `change_summary` cites: the CTO Mode newsletter article
itself (received via email, message_id `19ef0107615589f6`, read in full
during this session — the content came through Gmail, not a web fetch);
the two disclosed attack classes it reports (Microsoft's "AutoJack"
disclosure, "Agentjacking" research attributed to Tenet against 100+
organizations); and Simon Willison's "lethal trifecta" framing, which the
article itself attributes rather than this session verifying against
Willison's original writing directly. This last attribution is stated as
"per the source article," not as independent verification — accurate about
the actual provenance chain, not overclaiming.

### 3. `always_apply: false`, `phase_scope` covers design and build

**Decision.** Matches `incident-response`'s `always_apply: false` — relevant
when a task touches MCP/tool configuration or agent permission review, not
universally relevant the way `test-driven-development` is.
`phase_scope: [design, build]` — relevant when a task is actively deciding
what tools/permissions an agent gets (design) or wiring them up (build).
`category_scope: [process]`, matching `incident-response`'s categorization
(a practice/discipline skill, not language- or framework-specific).

### 4. Pack version bump

**Decision.** `core/pack.yaml` version `2.0.6` → `2.0.7` (patch bump — one
new skill added, no breaking change to existing skills).

## Non-goals carried from spec

No PR, no merge — branch push only. No fix to the integrator-intake draft
content gap. No other corpus changes.
