# automation-risk-classifier — Design

## Approach

### 1. `str.startswith()` on directory prefixes, not glob matching

**Decision.** The allowlist is two directory prefixes
(`src/agentalloy/_packs/`, `docs/`) — `path.startswith(prefix)` after
normalizing both to use `/` and stripping any leading `./` is sufficient
and simpler than `fnmatch`/`Path.match()` glob semantics, which would add
complexity (glob edge cases, `**` semantics) for a case that doesn't need
it. Revisit if the allowlist ever needs real glob patterns (e.g.
excluding a specific file within an otherwise-allowed directory) — not
needed today.

```python
LOW_RISK_PATH_PREFIXES = (
    "src/agentalloy/_packs/",
    "docs/",
)

def classify(changed_paths: list[str]) -> Literal["low", "high"]:
    if not changed_paths:
        return "high"  # fail closed: no evidence is not evidence of safety
    if all(
        any(p.lstrip("./").startswith(prefix) for prefix in LOW_RISK_PATH_PREFIXES)
        for p in changed_paths
    ):
        return "low"
    return "high"
```

### 2. Empty input fails closed: `high`

**Decision (resolves the spec's open design question).** `classify([])`
returns `high`. This function exists specifically to gate autonomous
action; treating "no information" as "safe" would be the wrong default for
a safety gate, even though it's an edge case unlikely to occur in practice
(a real diff from a real change is never empty). Explicit, not `all()`'s
incidental vacuous-truth-is-True behavior — the code short-circuits on
empty input before reaching the `all()` call, so the decision is visible
in the code, not an accident of Python semantics.

### 3. A named, exported allowlist constant

**Decision.** `LOW_RISK_PATH_PREFIXES` is a module-level tuple, not buried
inside the function — so it can be imported and asserted against directly
in tests (AC1-AC3 partly test the constant's content, not just the
function's behavior on specific inputs), and so a future PR expanding it
is a one-line, highly visible diff to review.

## Non-goals carried from spec

No merge/deploy wiring. No allowlist expansion beyond the two prefixes
named in the spec. No SDD-execution generation — this classifies an
existing diff.
