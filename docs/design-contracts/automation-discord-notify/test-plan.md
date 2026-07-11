# automation-discord-notify — Test Plan

## Test Cases

### Task 1 — `report`

- **T1.1 (AC1).** Seed candidates with `evaluated_at` values before and
  after a cutoff; `report --since <cutoff>` includes only the
  at-or-after ones.
- **T1.2 (AC2).** One candidate each of `accept`/`needs_review`/`reject`
  in the window — accept and needs_review show message_id/subject/
  source/rationale in the output; reject appears only in the count, not
  itemized (its message_id/subject do not appear in the body text).
- **T1.3 (AC3, empty window).** `report --since <a time after everything>`
  → single-line "no candidates evaluated" output.
- **T1.4 (AC3, all-rejected window).** A window with only `reject`
  candidates → a short "nothing needs your attention, N rejected" line,
  no ACCEPT/NEEDS REVIEW section headers.
- **T1.5 (AC4, flagged present).** A window including a flagged candidate
  → output includes a one-line flagged-count mention.
- **T1.6 (AC4, flagged absent).** A window with zero flagged candidates →
  no flagged-related line anywhere in the output.

### Task 3 — live proof

- **T3.1 (AC6).** `uv run python -m automation.cli ingest report --since
  <a timestamp before last night's evaluation batch>` against the real
  production store — output shown, correctly reflecting the real
  accept/needs_review/reject breakdown from last night's 39 candidates
  (1 needs_review, rest reject, 0 accept — matches what's already known
  from memory).

### Task 4 — live webhook delivery (after Jay provides a URL and confirms)

- **T4.1 (AC7).** One real `curl` POST of real `report` output to the
  provided webhook URL; Jay confirms the message arrived in Discord
  correctly formatted before the live routine's configuration is updated.
