"""Gemma-4-as-critic-model trial harness.

Runs the same 15 (10 primary + 5 mutated) lesson-skill YAMLs through
``qa_gate.run_critic`` against a chosen critic model, timing each call and
writing one aggregate JSON per run so a baseline (``qwen3.6-27b``) run and a
candidate (Gemma 4 build) run never collide.

Usage:
    set -a && source ~/.config/agentalloy/agentalloy.env && set +a
    uv run python scripts/gemma_critic_trial.py --critic-model qwen3.6-27b
    uv run python scripts/gemma_critic_trial.py --critic-model <gemma-4-build-name>
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from pathlib import Path

from agentalloy.authoring.prompt_loader import load_prompt
from agentalloy.authoring.qa_gate import run_critic
from agentalloy.config import get_settings
from agentalloy.lm_client import OpenAICompatClient

REPO = Path(__file__).resolve().parents[1]

_PRIMARY_SLUGS = (
    "automation-auto-merge-gate",
    "automation-discord-notify",
    "automation-drive-sync",
    "automation-email-ingestion",
    "automation-evaluator-four-lens",
    "automation-evaluator",
    "automation-gemini-review",
    "automation-injection-guard",
    "automation-integrator-intake",
    "automation-risk-classifier",
)

_MUTATED_SLUGS = (
    "automation-injection-guard",
    "automation-gemini-review",
    "automation-evaluator",
    "automation-auto-merge-gate",
    "automation-drive-sync",
)

# (case_id, yaml_path, source_md_path) — source_md is always the real,
# unmutated docs/solutions/<slug>.md, even for the mutated cases. Mutated
# cases share their primary counterpart's yaml stem, so case_id disambiguates
# them (report filenames, aggregate JSON entries, and the diff script all key
# off case_id rather than the raw stem).
TARGETS: list[tuple[str, Path, Path]] = [
    *[
        (
            f"{slug}-lesson",
            REPO / ".agentalloy/custom-skills" / f"{slug}-lesson" / f"{slug}-lesson.yaml",
            REPO / "docs/solutions" / f"{slug}.md",
        )
        for slug in _PRIMARY_SLUGS
    ],
    *[
        (
            f"{slug}-lesson-mutated",
            REPO
            / "docs/qa/gemma-4-critic-model-trial/mutated-cases"
            / f"{slug}-lesson.yaml",
            REPO / "docs/solutions" / f"{slug}.md",
        )
        for slug in _MUTATED_SLUGS
    ],
]


def render_report(case_id: str, critic_model: str, verdict_obj) -> str:  # type: ignore[no-untyped-def]
    lines = [
        f"# Critic trial: {case_id}",
        "",
        f"- **Reviewer:** {critic_model} via qa_gate.run_critic (no dedup)",
        f"- **Verdict:** `{verdict_obj.verdict}`",
        f"- **Summary:** {verdict_obj.summary}",
        "",
    ]
    if verdict_obj.blocking_issues:
        lines += ["## Blocking issues", ""]
        lines += [f"- {b}" for b in verdict_obj.blocking_issues]
        lines.append("")
    if verdict_obj.per_fragment:
        lines += ["## Per-fragment notes", ""]
        for pf in verdict_obj.per_fragment:
            lines.append(f"- seq {pf.get('sequence', '?')}: {pf.get('note', '')}")
        lines.append("")
    if verdict_obj.suggested_edits:
        lines += ["## Suggested edits", "", verdict_obj.suggested_edits, ""]
    if verdict_obj.tag_verdicts:
        lines += ["## Tag verdicts", ""]
        for tv in verdict_obj.tag_verdicts:
            lines.append(
                f"- [{tv.get('rule', '?')}] {tv.get('tag', '?')}: "
                f"{tv.get('verdict', '?')} — {tv.get('detail', '')}"
            )
        lines.append("")
    return "\n".join(lines)


def _fs_safe(model_name: str) -> str:
    """Sanitize a critic-model id (e.g. 'google/gemma-4-e4b') for use as a
    single path component, so slashes in the model id can't be mistaken for
    directory separators."""
    return re.sub(r"[^A-Za-z0-9_.\-]", "-", model_name)


def parse_args() -> argparse.Namespace:
    settings = get_settings()
    ac = settings.require_authoring_config()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--critic-model",
        default=ac.critic_model,
        help=f"Critic model to run (default: {ac.critic_model})",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    critic_model = args.critic_model

    settings = get_settings()
    ac = settings.require_authoring_config()
    qa_prompt, version = load_prompt(REPO / "fixtures" / "skill-qa-agent.md")
    print(f"[init] critic={critic_model}  prompt_version={version or '(none)'}")
    client = OpenAICompatClient(ac.lm_studio_base_url)

    report_dir = REPO / "docs/qa/gemma-4-critic-model-trial" / _fs_safe(critic_model)
    report_dir.mkdir(parents=True, exist_ok=True)

    results: list[dict] = []
    for case_id, yaml_path, source_md_path in TARGETS:
        draft_text = yaml_path.read_text(encoding="utf-8")
        source_text = (
            source_md_path.read_text(encoding="utf-8")
            if source_md_path.exists()
            else "(source doc not found)"
        )
        print(f"[run ] {case_id}  ({len(draft_text)} bytes) → {critic_model}", flush=True)

        start = time.monotonic()
        verdict = run_critic(
            client=client,
            model=critic_model,
            qa_prompt=qa_prompt,
            source_md=source_text,
            draft_yaml_text=draft_text,
            soft_dups=[],
            semantic_tag_block="",
        )
        elapsed_s = time.monotonic() - start

        report_path = report_dir / f"{case_id}.critic.md"
        report_path.write_text(render_report(case_id, critic_model, verdict), encoding="utf-8")
        print(
            f"[done] {case_id}: {verdict.verdict} in {elapsed_s:.2f}s → "
            f"{report_path.relative_to(REPO)}"
        )

        results.append(
            {
                "case_id": case_id,
                "yaml_path": str(yaml_path.relative_to(REPO)),
                "verdict": verdict.verdict,
                "summary": verdict.summary,
                "blocking_issues": verdict.blocking_issues,
                "per_fragment": verdict.per_fragment,
                "tag_verdicts": verdict.tag_verdicts,
                "elapsed_s": elapsed_s,
            }
        )

    print("\n=== Summary ===")
    for r in results:
        print(f"  {r['verdict']:<8} {r['case_id']:<48} {r['elapsed_s']:.2f}s")

    agg_path = REPO / "docs/qa/gemma-4-critic-model-trial" / f"aggregate-{_fs_safe(critic_model)}.json"
    agg_path.write_text(json.dumps(results, indent=2), encoding="utf-8")
    print(f"\nWrote aggregate: {agg_path.relative_to(REPO)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
