# automation-auto-merge-gate — Design

## Approach

### 1. `automation/ci/auto_merge_gate.py` — thin stdin-to-classification wrapper

**Decision.** A single small script, same shape as `gemini_review.py`'s
`main()` but with no impure network call at all — `risk_classifier.classify()`
is already pure and already tested, so this file has nothing to isolate.
It exists only to give the workflow a CLI surface:

```python
import sys
from automation.risk_classifier import classify

def main() -> int:
    changed_paths = [line for line in sys.stdin.read().splitlines() if line]
    print(classify(changed_paths))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
```

`classify()` itself is imported unmodified — no re-implementation, no new
edge cases to reason about beyond "does stdin-splitting produce the same
list `classify` already handles." Blank-line filtering handles the
trailing-newline-from-`git diff`-output case cleanly (an empty line would
otherwise `.startswith("")` — true for any prefix — silently corrupting
the classification; explicit filtering avoids relying on that being
harmless by accident).

### 2. Workflow computes the diff the same safe way `gemini-review.yml` does

**Decision.** Reuse the exact `BASE_REF` env-var pattern fixed in
`gemini-review.yml` after a real finding (round 4: splicing a GHA
expression directly into a shell `run:` block is a script-injection risk).
No reason to introduce the same risk fresh in a new workflow when the safe
pattern already exists and is proven:

```yaml
env:
  BASE_REF: ${{ github.event.pull_request.base.ref }}
  GH_TOKEN: ${{ github.token }}
run: |
  set -o pipefail
  git diff --name-only "origin/$BASE_REF"...HEAD > /tmp/changed_paths.txt
  risk=$(uv run python -m automation.ci.auto_merge_gate < /tmp/changed_paths.txt)
  echo "Classified: $risk"
  if [ "$risk" = "low" ]; then
    gh pr merge "${{ github.event.pull_request.number }}" --auto --squash
  fi
```

`set -o pipefail` again as the first line — the exact false-positive-pass
lesson from `gemini-review.yml`'s round-1 bug applies to any pipeline in
this repo, not just that one file.

### 3. High-risk classification is silent — no PR comment

**Decision (resolves the spec's first open design question).** A `high`
result is a pure no-op: no `gh pr merge` call, no comment. Reasoning: this
workflow runs on every PR alongside `gemini-review.yml`, which already
posts a substantive comment every single time. A second bot comment
saying "this didn't happen" on every high-risk PR (the common case — most
real changes touch `automation/` or `src/agentalloy/` outside `_packs/`)
would be pure noise, not signal — the PR's own unchanged, still-pending
merge state already communicates "nothing automatic happened here."
Revisit only if it turns out to be non-obvious in practice why a given PR
isn't auto-merging.

### 4. Required-check list: all five existing checks

**Decision (resolves the spec's second open design question).** Branch
protection on `main` requires exactly the five checks that already exist
and already have a real, live-tested track record tonight: `quality`,
`review`, `container-tests`, `web-build`, `pipx-smoke`. No subsetting —
every one of the five has caught something real this session (quality:
the import-sort/format debt; review: ten findings across four rounds;
the others already gate correctness/build integrity by design). Excluding
any of them from the auto-merge gate would mean a genuinely broken
low-risk PR could pass the excluded check silently.

### 5. Branch protection does *not* set "include administrators"

**Decision (resolves the spec's third open design question).** Jay merged
both PR #9 and PR #10 manually tonight without friction. Restricting his
own merges to the same required-check gate as automation would be a real
behavior change to his existing workflow that nobody asked for — this
slice's goal is adding a new automatic path for low-risk changes, not
constraining the existing manual path. If Jay later wants his own merges
gated too, that's a one-setting change, made deliberately, not a side
effect of this slice.

### 6. Settings changes and live-proof PRs are explicit checkpoints, not build steps

**Decision.** The build phase produces only new files
(`automation/ci/auto_merge_gate.py`, its tests, the new workflow) and gets
those reviewed/merged through the normal PR flow — same as every prior
slice tonight, no different ceremony. The two GitHub settings changes
(branch protection, `allow_auto_merge`) and the two live-proof PRs (one
genuinely low-risk, one genuinely high-risk) happen only after this
slice's own PR is merged and Jay has given a fresh, explicit go-ahead —
named as its own step in tasks.md, not folded into "ship."
