# automation-pr-digest — Design

## Approach

### 1. `automation/ci/pr_digest.py` — pure bucketing/formatting function

**Decision.** `format_digest(prs: list[dict], since: str) -> str` takes
the raw list of PR records `gh pr list --json ...` produces (each with
`number`, `title`, `url`, `author`, `createdAt`, `mergedAt`, `state`,
`mergedBy`) and does all three bucketing decisions in pure Python:

```python
def format_digest(prs: list[dict[str, Any]], since: str) -> str:
    opened = [p for p in prs if p["createdAt"] >= since]
    merged = [p for p in prs if p.get("mergedAt") and p["mergedAt"] >= since]
    still_open = [p for p in prs if p["state"] == "OPEN"]

    if not opened and not merged and not still_open:
        return f"PR Digest — nothing to report since {since}."

    lines = [f"PR Digest — since {since}"]
    if opened:
        lines.append(f"\nOpened ({len(opened)}):")
        lines += [f"- #{p['number']} {p['title']} — {p['url']}" for p in opened]
    if merged:
        lines.append(f"\nMerged ({len(merged)}):")
        lines += [f"- #{p['number']} {p['title']} — {_merge_label(p)} — {p['url']}" for p in merged]
    if still_open:
        lines.append(f"\nStill open ({len(still_open)}):")
        lines += [f"- #{p['number']} {p['title']} — {p['url']}" for p in still_open]
    return "\n".join(lines)
```

"Still open" is a snapshot of *currently* open PRs, not filtered by the
window — this gives Jay a running view of pending work every digest, not
just PRs that happened to open in the last 24 hours (matches the actual
visibility need: "what's waiting on me / what might auto-merge soon").

### 2. Auto/manual merge label — isolated helper, degrades gracefully

**Decision (resolves the spec's `mergedBy` assumption).**

```python
def _merge_label(pr: dict[str, Any]) -> str:
    merged_by = pr.get("mergedBy")
    if not merged_by:
        return "merged"
    return "auto-merged" if merged_by.get("is_bot") else "manually merged"
```

A separate, tiny function rather than inlining the ternary into
`format_digest` — keeps the one genuinely unverified assumption (does
`gh pr merge --auto` under `GITHUB_TOKEN` actually produce
`mergedBy.is_bot: true`?) isolated to one place, easy to revisit once a
real auto-merged PR exists to check it against. Missing/null `mergedBy`
degrades to the label-free `"merged"` rather than guessing or raising.

### 3. `post_to_discord` — the one isolated impure call

**Decision.** Same shape as `gemini_review.py`'s `call_gemini`: stdlib
`urllib.request` only, no new dependency, reads the webhook URL from a
parameter (never a module-level constant or literal) so it's trivially
monkeypatchable in tests:

```python
def post_to_discord(message: str, webhook_url: str) -> None:
    body = json.dumps({"content": message}).encode()
    req = urllib.request.Request(
        webhook_url,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        resp.read()
```

### 4. `main()` — env reads inside the try from the start

**Decision.** Apply `gemini_review.py`'s round-3 lesson preemptively
rather than waiting to discover it live a second time: every env-var read
(`SINCE`, `DISCORD_WEBHOOK_URL`) lives inside the same `try` as the actual
work, so a missing var produces a clear stderr message and non-zero exit
rather than an unhandled traceback.

```python
def main() -> int:
    try:
        since = os.environ["SINCE"]
        webhook_url = os.environ["DISCORD_WEBHOOK_URL"]
        prs = json.loads(sys.stdin.read())
        message = format_digest(prs, since)
        post_to_discord(message, webhook_url)
    except Exception as exc:
        print(f"pr-digest failed: {exc}", file=sys.stderr)
        return 1
    print(message)
    return 0
```

Unlike `gemini_review.py`, there's no PR to comment on here (this is a
scheduled job, not a per-PR check), so a failure surfaces as a normal
GitHub Actions job failure — visible in the Actions tab, sufficient for a
visibility feature with no merge decision riding on it.

### 5. Workflow: `gh pr list` needs no `--repo` flag, and `SINCE` is exported

**Decision.** Running inside the checked-out repo, `gh` infers the repo
from git config — no `--repo` argument needed, which also sidesteps
needing to decide whether `github.repository` counts as safe to splice
into the shell string (moot either way, but simpler to just not need it).
`SINCE` is computed and `export`ed as a real shell env var so the `uv run
python -m automation.ci.pr_digest` subprocess inherits it — module
invocation from the start (the exact fix `auto-merge-gate.yml` needed
live, applied here without needing to rediscover it):

```yaml
env:
  GH_TOKEN: ${{ github.token }}
  DISCORD_WEBHOOK_URL: ${{ secrets.DISCORD_WEBHOOK_URL }}
run: |
  set -o pipefail
  export SINCE=$(date -u -d '24 hours ago' +%Y-%m-%dT%H:%M:%SZ)
  gh pr list --state all --limit 100 \
    --json number,title,url,author,createdAt,mergedAt,state,mergedBy \
    > /tmp/prs.json
  uv run python -m automation.ci.pr_digest < /tmp/prs.json
```

### 6. Schedule: daily at 13:00 UTC, plus `workflow_dispatch`

**Decision (resolves the spec's schedule-interval design question).**
13:00 UTC = 9am America/New_York in summer — a "start your day" digest,
roughly parallel to the existing candidate-evaluation routine's 7:12 AM ET
schedule without exactly overlapping it. `workflow_dispatch` is always
available for on-demand runs, used for this slice's own live proof so
shipping doesn't have to wait for the next scheduled fire. Jay can trivially
adjust the cron expression later if daily isn't the cadence he wants.

### 7. Plain text, not a Discord embed

**Decision (resolves the spec's message-format design question).**
Matches `automation-discord-notify`'s precedent exactly — plain text with
blank-line-separated sections already proved sufficient for that digest's
real content; no reason to introduce embed complexity here for a
structurally similar message.
