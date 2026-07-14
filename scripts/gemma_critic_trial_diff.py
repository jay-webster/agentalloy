"""Diff two gemma_critic_trial.py aggregate JSON runs (baseline vs candidate).

For every case: verdict agreement, blocking_issues set-difference, and
elapsed_s ratio. For the 5 mutated cases (case_id ending in "-mutated",
sourced from docs/qa/gemma-4-critic-model-trial/mutated-cases/): a
best-effort keyword/substring check of the case's sibling .defect.md against
each run's blocking_issues text — reported per case, never silently dropped.

Usage:
    uv run python scripts/gemma_critic_trial_diff.py \\
        docs/qa/gemma-4-critic-model-trial/aggregate-qwen3.6-27b.json \\
        docs/qa/gemma-4-critic-model-trial/aggregate-<gemma-4-build>.json
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]

_STOPWORDS = {
    "the",
    "a",
    "an",
    "and",
    "or",
    "but",
    "of",
    "to",
    "in",
    "on",
    "for",
    "with",
    "as",
    "is",
    "was",
    "were",
    "be",
    "been",
    "being",
    "this",
    "that",
    "it",
    "its",
    "at",
    "by",
    "from",
    "into",
    "not",
    "no",
    "any",
    "one",
    "exactly",
    "named",
    "violation",
    "rule",
    "sentence",
}


def _load_aggregate(path: Path) -> dict[str, dict]:
    entries = json.loads(path.read_text(encoding="utf-8"))
    return {e["case_id"]: e for e in entries}


def _keywords(text: str) -> set[str]:
    words = re.findall(r"[a-zA-Z0-9_.\-]{3,}", text.lower())
    return {w for w in words if w not in _STOPWORDS}


def _blocking_text(entry: dict) -> str:
    return " ".join(entry.get("blocking_issues") or []).lower()


def _defect_md_path(entry: dict) -> Path | None:
    yaml_path = REPO / entry["yaml_path"]
    if "mutated-cases" not in yaml_path.parts:
        return None
    return yaml_path.with_suffix("").with_suffix(".defect.md")


def _defect_hit(defect_text: str, blocking_text: str) -> tuple[bool, set[str]]:
    """Best-effort: does blocking_text mention enough of the defect's keywords?"""
    defect_keywords = _keywords(defect_text)
    if not defect_keywords:
        return False, set()
    matched = {kw for kw in defect_keywords if kw in blocking_text}
    # Best-effort threshold: at least 2 distinct keyword hits, or >=25% of
    # the defect's keywords, whichever is more lenient for short defects.
    hit = len(matched) >= 2 or (defect_keywords and len(matched) / len(defect_keywords) >= 0.25)
    return hit, matched


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "baseline_json", type=Path, help="Aggregate JSON from the baseline critic model run"
    )
    parser.add_argument(
        "candidate_json", type=Path, help="Aggregate JSON from the candidate critic model run"
    )
    args = parser.parse_args()

    baseline = _load_aggregate(args.baseline_json)
    candidate = _load_aggregate(args.candidate_json)

    all_case_ids = list(dict.fromkeys([*baseline.keys(), *candidate.keys()]))
    missing_baseline = [c for c in all_case_ids if c not in baseline]
    missing_candidate = [c for c in all_case_ids if c not in candidate]
    if missing_baseline:
        print(f"[warn] cases missing from baseline run: {missing_baseline}")
    if missing_candidate:
        print(f"[warn] cases missing from candidate run: {missing_candidate}")

    agreements = 0
    compared = 0
    ratios: list[float] = []
    mutated_rows: list[tuple[str, bool, bool]] = []

    print("=== Per-case diff ===\n")
    for case_id in all_case_ids:
        b = baseline.get(case_id)
        c = candidate.get(case_id)
        if b is None or c is None:
            print(f"[{case_id}] SKIPPED — missing from one run\n")
            continue

        compared += 1
        agree = b["verdict"] == c["verdict"]
        agreements += int(agree)

        b_issues = set(b.get("blocking_issues") or [])
        c_issues = set(c.get("blocking_issues") or [])
        only_baseline = b_issues - c_issues
        only_candidate = c_issues - b_issues

        ratio = None
        if b.get("elapsed_s") and b["elapsed_s"] > 0:
            ratio = c.get("elapsed_s", 0.0) / b["elapsed_s"]
            ratios.append(ratio)

        print(f"[{case_id}]")
        print(f"  verdict: baseline={b['verdict']!r} candidate={c['verdict']!r} agree={agree}")
        if only_baseline:
            print(f"  only baseline flagged: {sorted(only_baseline)}")
        if only_candidate:
            print(f"  only candidate flagged: {sorted(only_candidate)}")
        if ratio is not None:
            print(f"  latency ratio (candidate/baseline): {ratio:.2f}x")
        else:
            print("  latency ratio: n/a (baseline elapsed_s missing/zero)")

        defect_path = _defect_md_path(b)
        if defect_path is not None:
            if not defect_path.exists():
                print(f"  [mutated] MISSING .defect.md at {defect_path.relative_to(REPO)}")
                mutated_rows.append((case_id, False, False))
            else:
                defect_text = defect_path.read_text(encoding="utf-8")
                b_hit, b_matched = _defect_hit(defect_text, _blocking_text(b))
                c_hit, c_matched = _defect_hit(defect_text, _blocking_text(c))
                print(f"  [mutated] defect: {defect_text.strip()}")
                print(
                    f"  [mutated] baseline caught it: {b_hit} (matched keywords: {sorted(b_matched)})"
                )
                print(
                    f"  [mutated] candidate caught it: {c_hit} (matched keywords: {sorted(c_matched)})"
                )
                mutated_rows.append((case_id, b_hit, c_hit))
        print()

    print("=== Summary ===")
    if compared:
        print(f"Verdict agreement: {agreements}/{compared} ({100 * agreements / compared:.0f}%)")
    else:
        print("Verdict agreement: n/a (no comparable cases)")
    if ratios:
        print(
            f"Mean latency ratio (candidate/baseline): {sum(ratios) / len(ratios):.2f}x over {len(ratios)} cases"
        )
    else:
        print("Mean latency ratio: n/a")

    print("\nMutated-case defect-catch table:")
    print(f"  {'case_id':<48} {'baseline':<10} {'candidate':<10}")
    for case_id, b_hit, c_hit in mutated_rows:
        print(f"  {case_id:<48} {str(b_hit):<10} {str(c_hit):<10}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
