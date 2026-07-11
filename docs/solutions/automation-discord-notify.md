# automation-discord-notify — Lesson

## Problem

The scheduled routine runs unattended, but nothing surfaces its results —
Jay would have to manually check run history or the Drive-hosted db to
know anything happened. Close the loop with Discord, the notification
channel the original pipeline vision named from the start.

## What worked

**Recognizing that a connector-availability problem doesn't always need a
connector-shaped fix.** Discord, like Gmail, isn't reachable from a
routine's cloud sandbox — but unlike Gmail (which genuinely required a
multi-hop bridge through Apps Script and Drive), Discord's incoming
webhooks are just a plain HTTPS endpoint. A routine's `Bash`/`curl` can hit
it directly, no connector, OAuth, or bridge needed. Checking *how* the
target service actually works before assuming the same class of fix
applies avoided building unnecessary infrastructure.

**Basing the reporting window on a captured timestamp rather than new
tracking state.** `evaluated_at >= since`, with `since` captured by the
routine itself right before it starts evaluating, gives an exact "what did
this run just do" scope without adding a new column, a new "last reported
at" marker, or any coordination between runs. The store didn't need to
know anything new about "runs" as a concept.

**Live-proving the report command against real, independently-known
data.** Running `ingest report` against the real 39-candidate database and
getting back exactly the breakdown already recorded in memory from two
separate sessions' worth of real evaluation work is stronger evidence than
a synthetic fixture could provide — the test data wasn't constructed to
make this feature look correct; it already existed for unrelated reasons.

## What didn't work / had to be corrected

Nothing required correction in the shipped code — same as the last two
slices, design held on first implementation. The one honest incompleteness
(AC7, webhook delivery) isn't a mistake to fix; it's a real external
dependency (Jay's own Discord webhook) that can't be resolved by writing
more code.

## Decisions worth keeping

- Before assuming a "not available as a connector" problem needs a bridge
  as complex as the last one, check whether the target service has a
  simpler native mechanism (a webhook, a plain API) that sidesteps the
  connector question entirely.
- A reporting/digest feature scoped by "since a captured timestamp" is
  simpler and more robust than trying to track "have I already reported
  this candidate" as new persistent state — let the caller (the routine)
  own the concept of "a run," not the store.
- When a real, independently-sourced dataset already exists, prefer
  proving new read-only functionality against it over constructing a fresh
  fixture — the proof is stronger and costs nothing extra to obtain.
