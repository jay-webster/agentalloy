---
phase: spec
task_slug: symbol-linked-rationale
route: full
domain_tags:
  - knowledge-module
  - code-index
  - skill-authoring
  - lessons-promote
scope:
  touches:
    - "src/agentalloy/install/lesson_pack.py"
    - "src/agentalloy/install/subcommands/lessons.py"
    - "src/agentalloy/code_index/api/symbols_router.py"
    - "docs/spec/symbol-linked-rationale.md"
    - "tests/**"
  avoids:
    - "src/agentalloy/retrieval/**"
    - "src/agentalloy/code_index/retrieval/**"
    - "src/agentalloy/api/proxy_signal.py"
success_criteria: []
related_contracts: []
created_at: 2026-07-09T00:00:00Z
---

# symbol-linked-rationale

## Scope in a sentence

When a promoted lesson names the code symbols its rationale explains, record a
queryable link `(repo_slug, qualified_name) -> skill_id` so a symbol lookup can
surface why it's the way it is — the first slice of the Knowledge module's
"decisions graph linking rationale to symbols."

## Spec

Acceptance criteria and out-of-scope live in `docs/spec/symbol-linked-rationale.md`
(the runtime path). The committed copy of that spec doc is
`docs/spec-contracts/symbol-linked-rationale.spec.md`.

> Runtime note: a live contract's home is
> `.agentalloy/contracts/spec/symbol-linked-rationale.md`, and the spec doc's is
> `docs/spec/symbol-linked-rationale.md` — both git-ignored SDD runtime paths.
> The tracked copies under `docs/spec-contracts/` are the committed, reviewable
> form of that spec-phase work-item. To arm a live run, copy this file to
> `.agentalloy/contracts/spec/symbol-linked-rationale.md` and the spec doc to
> `docs/spec/symbol-linked-rationale.md`.
