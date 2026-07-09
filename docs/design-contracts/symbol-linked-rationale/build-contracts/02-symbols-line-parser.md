---
phase: build
task_slug: 02-symbols-line-parser
route: full
# domain_tags: 1-2 tags, ONE dominant tech surface — never every surface.
# Build retrieval is ~4 skills per contract; a 7-tag basket starves most
# surfaces (important fragments truncate, scores muddy). Keep it narrow.
domain_tags:
  - python
scope:
  touches:
    - "src/agentalloy/install/lesson_pack.py"
  avoids:
    - "src/agentalloy/code_index/**"
    - "src/agentalloy/storage/**"
success_criteria:
  - "a Symbols: line parses into an exact list of names, dots/colons preserved, not slugified"
  - "no Symbols: line yields an empty list -- never a derived-from-id fallback (unlike tags)"
related_contracts:
  - ".agentalloy/contracts/build/03-promote-symbol-wiring.md"
created_at: 2026-07-09T21:02:23Z
---

# 02-symbols-line-parser

## Task

In `src/agentalloy/install/lesson_pack.py`, add `_SYMBOLS_RE` (same regex
shape as the existing `_TAGS_RE` at the top of the file, just matching
`symbols` instead of `tags`) and a new function `_lesson_symbols(text: str) ->
list[str]`, sibling to the existing `_lesson_tags(text, skill_id)`. Key
difference from `_lesson_tags`: **do not slugify**. `_lesson_tags` lowercases
and replaces non-alphanumeric characters with `-` (correct for tags, wrong
here — a qualified name like `agentalloy.retrieval.domain.skill_granular_select`
has load-bearing dots). `_lesson_symbols` splits the matched line on `[,;]`
(same separator convention as tags) and only strips surrounding whitespace
per entry — no case-folding, no character substitution, exact text preserved.
Unlike `_lesson_tags`, there is no derived fallback when no `Symbols:` line is
present — return `[]` (there's no sensible default for a code symbol the way
`_derive_domain_tags` has one for tags).

Do not wire this into `generate_lesson_pack` or `promote_lesson` yet — that's
task 03. This task is the parser in isolation.

## Test cases

From `docs/design/symbol-linked-rationale/test-plan.md`, Task 2 section:
T2.1 (dots preserved, not slugified: `"Symbols: pkg.foo.Bar, pkg.baz"` →
`["pkg.foo.Bar", "pkg.baz"]`), T2.2 (no `Symbols:` line → `[]`, no fallback),
T2.3 (semicolon separator and extra whitespace parse the same as commas).

## Plan

Approach + full task order live in `docs/design/symbol-linked-rationale/`
(`approach.md` §2, `tasks.md` task 2). No dependency on other tasks;
`03-promote-symbol-wiring` depends on this one.
