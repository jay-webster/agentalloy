# authoring-critic-model-setup-docs — QA Report

## Checks

- **Accuracy check (AC1)**: `AuthoringConfig` in `src/agentalloy/config.py`
  read directly (lines 17-34) and compared field-by-field against the new
  subsection's table — `model="qwen3-14b-instruct"`,
  `critic_model="qwen3.6-27b"`, `lm_base_url="http://localhost:11435"`,
  `lm_studio_base_url="http://localhost:11434"` all match exactly. Step
  ownership (author/revise uses `ac.model`+`ac.lm_base_url`; QA/critic
  uses `ac.critic_model`+`ac.lm_studio_base_url`) confirmed against real
  usage in `authoring/pipeline.py:80,117,139`, `authoring/driver.py:147,269`,
  `authoring/__main__.py:204,211,222` — not guessed.
- **Link verification (AC2)**: all three Hugging Face URLs curled directly,
  all returned `200`:
  - `https://huggingface.co/unsloth/Qwen3.6-27B-GGUF` — 200
  - `https://huggingface.co/unsloth/Qwen3.6-27B-UD-MLX-4bit` — 200
  - `https://huggingface.co/unsloth/Qwen3.6-27B-MLX-8bit` — 200
- **Scope check (AC4)**: `git diff --stat main` shows exactly one file,
  `docs/operator.md` (37 insertions, 0 deletions). Zero diff under
  `src/agentalloy/`.
- **Apple-Silicon-only scoping (AC3)**: the subsection's own heading line
  reads "verified against a 48GB M4 Pro Mac Mini; NVIDIA/AMD/CPU-only
  guidance not yet written" — explicit, not implied universality.
- **Rendered Markdown (AC5)**: table and link syntax read correctly on
  direct inspection of the diff (see build phase transcript) — no
  malformed rows, no broken link brackets.

## Review

### Acceptance criteria (against `docs/spec-contracts/authoring-critic-model-setup-docs.spec.md`)

1. **Two-model split accurately described — MET.** See Checks, accuracy
   check.
2. **At least one real HF link per format (MLX, GGUF), accurate sizes —
   MET.** Three links given (one GGUF, two MLX precisions); all live,
   sizes match what this session's earlier research found (26.2GB/34.7GB
   MLX, ~18GB GGUF).
3. **Explicitly scoped to Apple Silicon — MET.** See Checks.
4. **No code touched — MET.** See Checks, scope check.
5. **Live proof (rendered correctly) — MET.** See Checks.

### Non-goals respected

Checked against the spec's Out of Scope: no automated puller built for
the authoring pipeline's models; no NVIDIA/AMD/CPU guidance fabricated
(explicitly named absent instead); the author model
(`AuthoringConfig.model`, `qwen3-14b-instruct`) documented only as part
of the existing env-var table (its default was already accurate and
worth including for completeness of the *table*), not given new
model-source research the way the critic model was — no new claims made
about it beyond what was already true; `critic_model`'s default value
untouched; no preflight check added (matches the assumption that
`ensure_model_loaded()` already covers this).

### Design conformance

Matches `approach.md` on every decision: subsection placed exactly where
specified (§1); env-var table reuses the existing table style byte-for-
byte (§2); GGUF 4-bit stated as the recommended default with MLX
4-bit/8-bit as explicit alternatives, not silently ranked (§3); no TOC or
cross-reference update needed, confirmed by inspection (§4).

### Findings

- **Critical**: none.
- **Dead code**: none — N/A, no code in this slice.
- **Nothing to report**: this was a small, precisely-scoped docs addition
  and every acceptance criterion was verifiable by direct inspection or a
  live link check; no ambiguity surfaced during build.

## Verdict

Clean. All 5 acceptance criteria met, all verifiable by direct evidence
(file diff, live HTTP checks, direct code comparison) rather than
judgment calls. Docs-only, zero risk to product code, falls within
`risk_classifier`'s low-risk allowlist (`docs/`) — eligible for auto-merge
once opened, though whether to let it auto-merge or review manually is
Jay's call at PR time.
