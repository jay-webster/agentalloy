# automation-discord-notify — Design

## Approach

### 1. `report`: query by `evaluated_at`, format by verdict tier

**Decision.** `automation/cli.py`, new `_cmd_report`:

```python
def _cmd_report(args, store) -> int:
    rows = [c for c in store.list() if c.evaluated_at and c.evaluated_at >= args.since]
    accepted = [c for c in rows if c.verdict == "accept"]
    needs_review = [c for c in rows if c.verdict == "needs_review"]
    rejected = [c for c in rows if c.verdict == "reject"]
    flagged = [c for c in rows if c.flagged]
    ...
```

String comparison on ISO 8601 UTC timestamps is lexicographically correct
(no need to parse to `datetime` for the `>=` filter) — same trick already
implicit in every other timestamp field in this store.

Output shape:

```
Automation run digest — 5 evaluated (2 accept, 1 needs_review, 2 reject)

ACCEPT:
- <message_id> | <source> | <subject>
  <rationale>

NEEDS REVIEW:
- <message_id> | <source> | <subject>
  <rationale>

1 candidate flagged by the injection guard this run.
```

When `rows` is empty: print a single line, `f"Automation run digest — no
candidates evaluated since {since}."`, and return — no section headers, no
zero-counts.

When there are evaluated rows but none are `accept`/`needs_review`
(everything rejected): print the summary line and a `"Nothing needs your
attention — N rejected."` line, skipping the (empty) ACCEPT/NEEDS REVIEW
sections entirely — this is the "short positive statement" AC3 asks for,
generalized to the "all rejected" case too, not just the "nothing
evaluated" case.

### 2. Plain text, not Discord embeds

**Decision (resolves the spec's open design question).** Discord's
incoming-webhook API accepts a bare `{"content": "..."}` JSON payload for
plain text, which is sufficient for every AC. Embeds add payload structure
(fields, colors, timestamps) with no functional requirement behind them —
skip until a real need appears.

### 3. Routine update: capture `since` at the right point, curl after report

**Decision.** `scheduled-drive-sync.md`'s step 4 (evaluate) gains a
preceding sub-step: capture `SINCE=$(date -u +%Y-%m-%dT%H:%M:%SZ)` *before*
running any `ingest evaluate` calls (so the window covers everything this
run touches, not just candidates evaluated after some other point). After
step 4 completes, run `uv run python -m automation.cli ingest report
--since "$SINCE"`, then POST its output to the webhook:

```bash
curl -X POST -H "Content-Type: application/json" \
  -d "$(jq -n --arg content "$(uv run python -m automation.cli ingest report --since "$SINCE")" '{content: $content}')" \
  "<webhook URL>"
```

(`jq -n --arg` correctly handles JSON-escaping the digest text, including
newlines and quotes — safer than hand-building the JSON string.) This runs
before the existing Drive-upload step, but ordering between the two
doesn't matter functionally — the report has already been generated from
in-memory/local db state by this point regardless of Drive's contents.

### 4. Webhook URL lives only in the routine's own config

**Decision.** Never written to any file in the repo, gitignored or
otherwise — it's routine-specific configuration, updated via `RemoteTrigger
action: update` directly, the same way the routine's prompt itself was
never committed to the repo as a file. This matches how the routine's
prompt already references Drive filenames as literals without needing a
shared config file — the webhook URL is one more literal the routine's own
configuration carries.

## Non-goals carried from spec

No other notification channel. No two-way Discord interaction. No
message-length truncation. No change to evaluation logic itself.
