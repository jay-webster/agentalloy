# Automation Discord Relay — Spec

> **Scope in a sentence.** Replace the `repository_dispatch` + PAT relay
> path (added ad hoc in `6a5f170`/`deb436a`, never spec'd) with a way to get
> the drive-sync routine's digest into Discord that doesn't require a
> repo-write-scoped secret to sit in plaintext inside the `RemoteTrigger`
> prompt.

> **Location note.** At runtime the SDD spec phase writes the spec to
> `docs/spec/automation-discord-relay.md`, git-ignored. This file is the
> committed, reviewable copy.

## Context

`automation-discord-notify.spec.md` shipped with one core assumption:
"a routine's `Bash` tool can `curl` a webhook directly." That assumption
was wrong — the first live run (`2026-07-12`) got a `403` from the
`RemoteTrigger` cloud environment's own network egress policy blocking
`discord.com` outright, not from anything about the webhook itself.

The fix applied at the time (`6a5f170`, `deb436a`) was a production patch,
not a spec'd design: relay the digest through a `repository_dispatch`
event to a GitHub Actions workflow (`discord-digest-relay.yml`, unrestricted
egress), which then does the actual Discord POST. That requires a GitHub
PAT to authenticate the `dispatches` call.

Re-verified directly against the live trigger (`trig_015i5taDUbLn7wHfbhb6BT5V`)
on `2026-07-14`: `job_config.ccr` has exactly three keys —
`environment_id`, `events`, `session_context` — no secrets/env-var facility
anywhere in the schema. There is no mechanism for that PAT to exist other
than as a literal string inside the same prompt-content field the webhook
URL already occupies. Unlike the webhook URL (scoped to posting into one
Discord channel, revocable with zero blast radius elsewhere), a PAT capable
of authenticating `repository_dispatch` needs write-level repo permissions
— a materially larger exposure for the same "sits in plaintext in a config
field" risk the original spec already accepted for the webhook URL.

## Assumptions (correct these before design)

- **The egress block is on the environment, not on Discord's endpoint
  specifically.** Unconfirmed whether `env_01Pi4vyrBN3EgidxBU8DtZoo` (or
  the `RemoteTrigger`/CCR platform generally) offers any egress-allowlist
  configuration that could permit `discord.com` directly, which would
  remove the need for *any* relay or second secret. This is the first
  thing design should check — it may make everything below moot.
- **If a relay is still needed, the credential's scope should be the
  smallest that works**, not whatever scope a first attempt happened to
  reach for. `repository_dispatch` was one option; it is not the only way
  to get a signal from this environment into a GitHub Actions run with
  unrestricted egress.
- **No new standing infrastructure without Jay's explicit sign-off.**
  Provisioning something like a dedicated relay endpoint (e.g. a small
  serverless function) is in-scope to *propose*, but stands up nothing on
  its own — same explicit-permission bar the original webhook config
  change already required.
- **The existing webhook-URL exposure (in the live trigger's prompt
  content) is not itself back in scope here.** That was an accepted
  assumption in the shipped `automation-discord-notify` spec; this spec is
  about the *additional* secret the relay pivot introduced, not re-opening
  the first one unless design finds the two are best solved together.
- **`discord-digest-relay.yml` and `pr_approved`/`pr_digest`'s existing
  Discord-posting path (`automation/ci/discord.py`) already prove GitHub
  Actions → Discord works reliably** — nothing about that leg of the
  pipeline needs to change; the open question is strictly "how does the
  `RemoteTrigger` routine authenticate to *reach* that leg."

## What

Not prescribed here — this is exactly the decision being deferred to
design (see Design surface). At minimum, whatever design is chosen must:

- Get the digest text produced by `ingest report --since <SINCE>` from the
  `RemoteTrigger` routine's execution into a Discord message, without
  depending on the routine reaching `discord.com` directly.
- Not require a secret with meaningfully broader scope than "cause one
  known digest message to be posted to one known Discord channel."
- Preserve the existing step-5/step-6 decoupling (`f6fc006`): a delivery
  failure in this mechanism must never block the Drive upload of the
  candidate store.

## Acceptance Criteria

1. **No credential used by the routine has repo write scope**, or broader
   permissions than strictly required to trigger delivery of one digest
   message. Verifiable by inspecting whatever token/credential the chosen
   design introduces against its documented minimum required scope.
2. **A real digest is delivered to the Discord channel end-to-end** via the
   new mechanism, confirmed with Jay in Discord — same live-proof bar as
   the original notify spec's AC7.
3. **A delivery failure in the new mechanism does not block or roll back
   the Drive upload step.** Verifiable by the same reasoning/tests as the
   existing step-5/step-6 decoupling, extended to cover the new failure
   modes this mechanism introduces (e.g. an expired or revoked credential).
4. **The chosen mechanism's secret, if any, is documented as
   routine-only config** (never committed to the repo, never typed or
   entered by an interactive Claude session) consistent with how the
   webhook URL is already handled — and that claim must be actually true
   of the live trigger schema, not aspirational (this spec exists because
   the previous relay's version of this claim wasn't).
5. **No product code touched** (`src/agentalloy/`) unless the chosen
   design specifically requires it, in which case the reason must be
   stated explicitly rather than assumed.

## Out of Scope

- **Revisiting the original webhook-URL exposure** in the shipped
  `automation-discord-notify` design, unless design finds the two problems
  share one natural fix.
- **Two-way interaction** — still send-only, unchanged from the original
  notify spec.
- **Any change to what the digest contains or how it's formatted** — that
  was already specified and shipped; this spec is purely about the
  transport/authentication leg.
- **Provisioning any new standing infrastructure** (e.g. a dedicated relay
  service) without a separate explicit go-ahead at the time it would
  actually be created.

## Design surface (hand-off to the design phase)

- **Whether the `RemoteTrigger`/CCR environment supports an egress
  allowlist** for `env_01Pi4vyrBN3EgidxBU8DtZoo` or an equivalent — if so,
  this entire relay may be unnecessary and the original direct-webhook
  design (already spec'd, already shipped in code) just starts working.
- **If a relay remains necessary, which GitHub Actions trigger type
  minimizes credential scope** — e.g. a fine-grained PAT scoped to
  `Actions: read and write` only (to fire a `workflow_dispatch`) is
  narrower than one scoped to `Contents: read and write` (required for
  `repository_dispatch`), since it can trigger a run but can't touch repo
  contents.
- **Whether a non-GitHub relay (e.g. a minimal serverless endpoint that
  only forwards to the existing Discord webhook) is worth the
  infrastructure cost** versus accepting a narrowly-scoped GitHub credential
  as "good enough" — a real tradeoff between blast radius and operational
  simplicity, not a foregone conclusion either way.
