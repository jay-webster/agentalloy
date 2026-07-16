# drive-sync-blockers — Lesson

## Problem

Jay asked to pursue two named blockers before the next scheduled Drive-sync
run: a `discord.com` 403 from the CCR environment's egress policy, and "the
drive error." Investigation showed "the drive error" was a much bigger,
previously-unknown bug than expected: the candidate store
(`agentalloy-automation-candidates.db`) had never once been created in
Google Drive, on any run to date — a silent, independent failure mode from
the Discord issue, meaning every run's evaluation work may never have
persisted regardless of whether the Discord notification succeeded.

## What worked

**Treating "the store has never landed in Drive" as its own hypothesis to
verify directly, not an assumption to build on.** A `Google-Drive`
`search_files` query for the store's exact filename, and a broader
recent-files listing, both came back with zero matches — ruling out a
query-syntax mistake and confirming the gap was real before any fix was
proposed.

**Reading the live trigger's actual `job_config` rather than trusting the
repo's routine doc alone.** The routine doc (`automation/routines/
scheduled-drive-sync.md`) already had the correct step-6/step-5 decoupling
language from a prior fix. The real trigger config, fetched via
`RemoteTrigger action=get`, showed the actual root cause: `mcp_connections`
had a `Google-Drive` connector attached, but `job_config.ccr.
session_context.allowed_tools` never listed any Drive MCP tool name at all.
The connector being *wired up* said nothing about whether the session was
*authorized* to call it — those are two separate layers, and only checking
the live config (not the doc, not the connector's mere presence) surfaced
the gap.

**Confirming the fix independently after applying it.** After calling
`RemoteTrigger action=update` to add the three required Drive tool names to
both `allowed_tools` and `mcp_connections[].permitted_tools`, a separate
`RemoteTrigger action=get` call (not just trusting the `update` response's
own echo) confirmed the change actually persisted server-side.

**Asking before modifying a live, persistent automation's config.**
Modifying `allowed_tools`/`mcp_connections` on a production scheduled
trigger is a standing-configuration change with real side effects (it
changes what every future scheduled run can do) — confirmed with Jay via
`AskUserQuestion` before calling `action=update`, rather than treating
"pursue the blockers" as blanket authorization for that specific
irreversible-ish change.

## What didn't work / had to be corrected

**The plain `.agentalloy/cursor` file went stale across phase advances,
same gotcha as [[gemma-4-critic-model-trial]].** `agentalloy task start
<slug>` writes a session-scoped cursor, but `agentalloy phase set` and the
gate banners read the plain, unscoped `.agentalloy/cursor` file — which
still pointed at an unrelated prior task (`authoring-critic-model-setup-docs`)
after every `phase set` advance in this session. Worked around by writing
`printf '<phase>/<slug>.md' > .agentalloy/cursor` directly after each
`task start` call, same as the documented fix from the prior lesson. This
is now the second time this exact gotcha has bitten a session — worth a
real CLI fix (`task start` writing both files, or gate predicates reading
the session-scoped file when available) rather than a third manual
workaround next time.

**The qa → ship exit gate wants `docs/solutions/<slug>.md` to exist before
the live cron-fire outcome (AC3) can actually be confirmed.** This lesson
doc is being written with that one item still open (see Decisions below) —
the gate is per-task and deterministic (`eval_lessons_recorded`), so it
doesn't wait for external, time-delayed confirmation. Documenting the
open item honestly here rather than treating gate-satisfaction as
proof the whole task is finished.

## Decisions worth keeping

- When a connector shows up in `mcp_connections`, that is necessary but not
  sufficient for a CCR session to be able to call it — always check
  `session_context.allowed_tools` too, both entries have to agree.
- Verify a live-platform config change with a fresh read call after
  applying it, not just by trusting the mutating call's own response.
- A live, recurring automation trigger's config is a standing/persistent
  setting, not a one-off action — treat changing it like changing a
  webhook or filter rule: ask first, even under a broad "go fix this"
  instruction.

## Open follow-up (not yet resolved)

**AC3 — actual Drive persistence under a real cron fire — is still
unconfirmed as of this writing.** The fix is applied and verified at the
config level (`RemoteTrigger get` shows the right tool grants), but the
next *real* scheduled run is 2026-07-15T11:12Z. Check Google Drive for
`agentalloy-automation-candidates.db` after that run fires to close this
out. The `discord.com` egress 403 remains separately unresolved by Jay's
own choice (deferred, not a gap in this fix) — see
`automation/routines/scheduled-drive-sync.md`'s Notes section.
