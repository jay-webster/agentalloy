# mcp-tool-trust-guardrail — Tasks

## Tasks

1. **Author `src/agentalloy/_packs/core/mcp-tool-trust-guardrail.yaml`.**
   Full skill YAML per approach.md §1-3: metadata fields, `raw_prose`
   matching the concatenated fragments, 7 fragments in the stated order.
   No dependency on other tasks. Satisfies AC1, AC2, AC4, AC5.

2. **Update `src/agentalloy/_packs/core/pack.yaml`.** Add the new skill's
   entry (`skill_id`, `file`, `fragment_count: 7`) to the `skills` list;
   bump `version` to `2.0.7`. Depends on Task 1 (needs the real fragment
   count). Satisfies AC3.

3. **Validate.** Run `agentalloy validate-pack` (or equivalent) against
   the `core` pack directory; fix anything strict mode flags. Depends on
   Tasks 1-2. Satisfies AC2, AC6.

4. **Push to a branch — no PR, no merge.** Commit the two changed files,
   push the branch to `origin`, stop. Depends on Task 3 passing. Satisfies
   AC6, AC7.
