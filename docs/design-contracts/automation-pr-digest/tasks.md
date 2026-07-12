# automation-pr-digest — Tasks

## Tasks

1. **`automation/ci/pr_digest.py` — pure functions.** `format_digest`,
   `_merge_label` per approach.md §1-2. No dependency on other tasks.
   Satisfies AC1.

2. **`post_to_discord` + `main()`.** The one impure function plus
   orchestration per approach.md §3-4. Depends on Task 1. Satisfies AC2.

3. **`.github/workflows/pr-digest.yml`.** Per approach.md §5-7. Depends on
   Tasks 1-2 (references the real script invocation). Satisfies AC3, AC4
   (by inspection — no webhook literal anywhere in the file), AC6.

4. **Live proof.** Once Jay confirms `DISCORD_WEBHOOK_URL` is set as a
   repo secret: trigger the workflow via `workflow_dispatch`, confirm a
   real message lands in Jay's Discord channel, inspected via the
   workflow run's conclusion (logs redacted by GitHub — never inspecting
   the raw webhook URL). Depends on Task 3 and Jay's action. Satisfies
   AC5.
