# automation-gemini-review — Tasks

## Tasks

1. **`automation/ci/gemini_review.py` — pure functions.** `build_prompt`,
   `parse_response`, `format_comment` per approach.md §1-3. No dependency
   on other tasks. Satisfies AC1, AC2, AC3.

2. **`call_gemini` + `main()`.** The one impure function plus
   orchestration per approach.md §3. Depends on Task 1. Satisfies AC4.

3. **`.github/workflows/gemini-review.yml`.** Per approach.md §4. Depends
   on Tasks 1-2 (references the real script invocation). Satisfies AC5,
   AC6 (by inspection — no key literal anywhere in the file).

4. **Live proof.** Once Jay confirms `GEMINI_API_KEY` is set as a repo
   secret: push this slice's own branch as a PR, confirm the workflow
   actually runs and reports a real pass/fail, inspected via `gh run
   view` (logs redacted by GitHub — never inspecting the raw key).
   Depends on Task 3 and Jay's action. Satisfies AC7.
