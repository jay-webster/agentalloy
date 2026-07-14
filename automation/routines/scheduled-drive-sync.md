# Routine: scheduled-drive-sync

Followed by a `RemoteTrigger` cloud routine, whose environment starts from
a fresh git clone every run and has no memory of prior runs beyond what it
explicitly fetches. The routine has a Google Drive MCP connector attached
(Gmail is not available to routines — see the drive-sync spec for why this
routine exists at all).

## Environment requirements

Attaching a `Google-Drive` entry under the trigger's `mcp_connections` is
**not sufficient** on its own for steps 1/2/6 below to work. The trigger's
`job_config.ccr.session_context.allowed_tools` must *also* explicitly list:

- `mcp__Google-Drive__search_files`
- `mcp__Google-Drive__download_file_content`
- `mcp__Google-Drive__create_file`

and the connector's own `mcp_connections[].permitted_tools` should mirror
the same three tool names. Without both, the session has no callable tool
for Drive search/download/upload — steps 1 and 2 silently degrade to "not
found, proceed anyway" (indistinguishable from a legitimate first run or
empty export) and step 6's upload has nothing to call at all. See Notes for
the real incident this caused.

## 1. Download the candidate store

Search Drive for `agentalloy-automation-candidates.db`. If found, download
it to `.automation/candidates.db` in the repo checkout. If not found (the
very first run ever), proceed with no local file — `CandidateStore`
creates the schema itself on first use, so there's nothing special to do
here.

## 2. Download the newsletter export

Search Drive for `agentalloy-automation-newsletter-export.jsonl`. If
found, download it to a local path. If not found, there is nothing new to
import — skip step 3 and continue to step 4 anyway (it will simply find no
`status=new` candidates, and step 5's report will correctly say so — this
still confirms to Jay that the routine ran).

## 3. Import

```
uv run python -m automation.cli ingest import-jsonl "<downloaded export path>"
```

This is safe to run even if some or all entries were already imported on a
prior run — `add()` is idempotent by `message_id`.

## 4. Evaluate

Before running any evaluation, capture the current time:

```
SINCE=$(date -u +%Y-%m-%dT%H:%M:%SZ)
```

Then follow `automation/routines/evaluate-candidate.md` (unchanged,
referenced here rather than duplicated) against `uv run python -m
automation.cli ingest list --status new`.

## 5. Relay the report to Discord via GitHub (best-effort — never blocks step 6)

Run:

```
uv run python -m automation.cli ingest report --since "$SINCE"
```

This environment's network egress policy blocks `discord.com` directly
(confirmed `403`, see Notes), so the report is relayed through a GitHub
Actions workflow (`discord-digest-relay.yml`, running on `ubuntu-latest`,
which has unrestricted egress) instead of posted to Discord directly.
Dispatch it with a `repository_dispatch` event, authenticated with
`GH_DISPATCH_TOKEN` (routine-only config, provisioned by Jay — never
committed to this repo and never typed or entered by Claude):

```
jq -n --arg report "$(uv run python -m automation.cli ingest report --since "$SINCE")" '{event_type: "discord-digest", client_payload: {report: $report}}' \
  | curl -sS -X POST \
      -H "Authorization: Bearer $GH_DISPATCH_TOKEN" \
      -H "Accept: application/vnd.github+json" \
      -d @- "https://api.github.com/repos/jay-webster/agentalloy/dispatches"
```

The `jq -n --arg` step correctly JSON-escapes the digest text (newlines,
quotes) — don't hand-build the JSON payload string directly.

**If this `curl` fails for any reason (including an auth or network
failure — the same class of real, confirmed failure mode that used to
hit `discord.com` directly, not hypothetical), do not stop the routine
and do not skip step 6.** Note the failure in the final report and
continue. A notification delivery failure says nothing about whether the
evaluation data itself is valid — gating persistence on it was a real bug
(see Notes) that lost a full run's evaluations (486 candidates) the first
time this environment's egress policy actually blocked the request.

## 6. Upload the candidate store back to Drive

Upload `.automation/candidates.db`, overwriting
`agentalloy-automation-candidates.db` in Drive, **as long as steps 1-4
completed without error — independent of whether step 5 (Discord)
succeeded.** This is the only step that matters for the *database* state
to persist into the next scheduled run; a real evaluation batch (486/486
processed, 0 errors) is valid, persistable data regardless of whether the
notification about it happened to get delivered. If step 1-4 genuinely
failed (corrupt import, a crash mid-evaluation), do NOT upload — stop and
report the error instead, so a partial or corrupt *data* state is never
persisted. A failed Discord POST is not that — see step 5.

## Notes

- The newsletter export file is not cleared or truncated by this routine —
  it grows over time on the Apps Script side (see
  `automation/appsscript/`). Re-importing old entries is harmless (step 3's
  idempotency) but not free; this is an accepted, low-urgency limitation
  given expected volume.
- This routine's Drive-hosted `candidates.db` is a separate, canonical copy
  for the routine's own use — it is not synced with any human's local
  `.automation/candidates.db` from an interactive session.
- **Real incident, 2026-07-12**: `discord.com` returned a `403` from this
  environment's network egress policy on the routine's very first
  Discord-enabled run, and step 6 was (at the time) gated on step 5
  succeeding — so a full, clean evaluation batch (486 candidates: 11
  accept, 32 needs_review, 443 reject, 0 errors) was never uploaded to
  Drive and was lost when the session ended. Fixed by decoupling step 6
  from step 5's outcome (see above). The underlying `discord.com` egress
  block is still unresolved — either the environment's egress policy
  needs `discord.com` allowed, or Discord delivery for this routine needs
  a different path entirely (e.g. bridging through the already-working
  GitHub Actions webhook delivery used by `pr-digest.yml`, which runs in
  a different, unrestricted network environment). Not yet decided.
- **Separate real incident, discovered 2026-07-14, fixed same day**: the
  live trigger's `mcp_connections` had a `Google-Drive` connector attached,
  but `session_context.allowed_tools` never actually listed any Drive MCP
  tool name — so, independent of and prior to the Discord issue above,
  steps 1/2/6 had no callable tool on *every* run to date, and
  `agentalloy-automation-candidates.db` had never once been created in
  Drive. Every run was silently re-importing and re-evaluating from an
  empty local store. Fixed by adding the three tool names to both
  `allowed_tools` and `mcp_connections[].permitted_tools` (see Environment
  requirements above) via a live `RemoteTrigger` config update on
  2026-07-14. Confirm this held by checking Drive for
  `agentalloy-automation-candidates.db` after the next scheduled run.
