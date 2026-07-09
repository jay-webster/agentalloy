---
phase: build
task_slug: 03-lesson-to-pack-generator
route: full
domain_tags:
  - skill-pack-authoring
scope:
  touches:
    - "src/agentalloy/install/**"
    - "tests/**"
  avoids:
    - "src/agentalloy/retrieval/**"
    - "src/agentalloy/api/**"
success_criteria: []
related_contracts: []
created_at: 2026-07-08T00:00:00Z
---

# 03-lesson-to-pack-generator

## Task

Build a generator that parses a `docs/solutions/<slug>.md` lesson into a valid
domain-skill pack under `.agentalloy/custom-skills/<slug>-lesson/`. Map lesson
content to fragments per the spec table: the approach that worked → `execution`;
how to confirm it → `verification`; the decision + what didn't work → `rationale`.
Emit a `pack.yaml` (tier `domain`, `embed_model` `nomic-embed-text-v1.5`,
`embedding_dim` 768) and a skill YAML with a valid production `category`,
`domain_tags` derived from the lesson's module/problem tags and clamped to the
domain soft ceiling, and `raw_prose` set to the ordered `\n\n` join of fragment
contents (satisfies the containment lint). Reuse `new_skill_pack`'s scaffold
shape where practical rather than hand-rolling the schema.

## Test cases

- TC4 (AC 4): generator output passes `agentalloy validate-pack` in strict mode
  (execution + verification + rationale fragments, valid category, tag ceiling,
  contiguous `raw_prose`).
- Edge: a lesson missing a "what didn't work" section still yields a non-empty
  `rationale` fragment (or fails loudly), never an invalid pack.
