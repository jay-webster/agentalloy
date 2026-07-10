# Routine: scheduled-drive-sync

Followed by a `RemoteTrigger` cloud routine, whose environment starts from
a fresh git clone every run and has no memory of prior runs beyond what it
explicitly fetches. The routine has a Google Drive MCP connector attached
(Gmail is not available to routines — see the drive-sync spec for why this
routine exists at all).

## 1. Download the candidate store

Search Drive for `agentalloy-automation-candidates.db`. If found, download
it to `.automation/candidates.db` in the repo checkout. If not found (the
very first run ever), proceed with no local file — `CandidateStore`
creates the schema itself on first use, so there's nothing special to do
here.

## 2. Download the newsletter export

Search Drive for `agentalloy-automation-newsletter-export.jsonl`. If
found, download it to a local path. If not found, there is nothing new to
import — skip to step 5.

## 3. Import

```
uv run python -m automation.cli ingest import-jsonl "<downloaded export path>"
```

This is safe to run even if some or all entries were already imported on a
prior run — `add()` is idempotent by `message_id`.

## 4. Evaluate

Follow `automation/routines/evaluate-candidate.md` (unchanged, referenced
here rather than duplicated) against `uv run python -m automation.cli
ingest list --status new`.

## 5. Upload the candidate store back to Drive

Upload `.automation/candidates.db`, overwriting
`agentalloy-automation-candidates.db` in Drive. This is the only step that
matters for state to persist into the next scheduled run — if this step is
skipped, everything done in steps 1-4 is lost.

## Notes

- The newsletter export file is not cleared or truncated by this routine —
  it grows over time on the Apps Script side (see
  `automation/appsscript/`). Re-importing old entries is harmless (step 3's
  idempotency) but not free; this is an accepted, low-urgency limitation
  given expected volume.
- This routine's Drive-hosted `candidates.db` is a separate, canonical copy
  for the routine's own use — it is not synced with any human's local
  `.automation/candidates.db` from an interactive session.
