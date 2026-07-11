# automation-auto-merge-gate — Tasks

## Tasks

1. **`automation/ci/auto_merge_gate.py`.** Per approach.md §1. No
   dependency on other tasks — `risk_classifier.classify()` already
   exists and is reused unmodified. Satisfies AC1.

2. **`.github/workflows/auto-merge-gate.yml`.** Per approach.md §2-3.
   Depends on Task 1 (references the real script invocation). Satisfies
   AC2, AC3.

3. **Scope check.** Confirm zero diff to `src/agentalloy/`,
   `automation/risk_classifier.py`, and every existing workflow file.
   Depends on Tasks 1-2. Satisfies AC3.

4. **GitHub settings change — explicit checkpoint.** Ask Jay directly,
   after this slice's own PR is merged, whether to enable branch
   protection on `main` (requiring `quality`, `review`, `container-tests`,
   `web-build`, `pipx-smoke`, per approach.md §4-5) and the repo's
   `allow_auto_merge` setting. Do not proceed to Task 5/6 without an
   explicit yes. Satisfies AC4.

5. **Live proof, low-risk path.** Once Task 4 is confirmed live: open a
   real PR touching only an allowlisted path (e.g. a `docs/` addition),
   confirm the new workflow enables auto-merge on it, and confirm it
   actually merges once required checks go green — with no manual `gh pr
   merge`. Depends on Tasks 2 and 4. Satisfies AC5.

6. **Live proof, high-risk path.** Confirm a PR touching a
   non-allowlisted path (e.g. `automation/`) does not get auto-merge
   enabled — stays a normal, manually-mergeable PR. Depends on Tasks 2
   and 4. Satisfies AC6.
