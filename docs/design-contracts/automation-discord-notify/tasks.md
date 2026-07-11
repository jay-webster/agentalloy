# automation-discord-notify — Tasks

## Tasks

1. **`automation/cli.py` — `ingest report --since <timestamp>`.** Per
   approach.md §1: filter by `evaluated_at >= since`, tiered output
   (accept/needs_review full detail, reject count-only, flagged
   count-only-if-nonzero), short positive statements for the empty and
   all-rejected cases. No dependency on other tasks. Satisfies AC1, AC2,
   AC3, AC4, AC5.

2. **`automation/routines/scheduled-drive-sync.md` update.** Per
   approach.md §3: capture `SINCE` before evaluation, run `ingest report`
   after, curl the output to the webhook (URL as a literal placeholder in
   the doc — the real URL lives only in the live routine's own config, per
   approach.md §4, never in this file). Depends on Task 1 (references its
   real command).

3. **Live proof of the testable half.** Run `ingest report --since
   <timestamp>` against the real production store (39 evaluated candidates
   from last night) with a window chosen to include some of them; show
   output. Depends on Task 1. Satisfies AC6.

4. **Live webhook delivery + routine update.** Once Jay provides a webhook
   URL and confirms: send one real `curl` POST of real digest output,
   confirm arrival in Discord with Jay, then update the live routine's
   configuration (`RemoteTrigger action: update`) to include the new step
   and URL. Depends on Task 2 (references the real routine content) and
   Jay's explicit go-ahead. Satisfies AC7.
