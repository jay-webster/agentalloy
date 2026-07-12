# Authoring Critic Model Setup Docs

> **Scope in a sentence.** Document which real, downloadable model artifact
> to load into LM Studio to satisfy agentalloy's `critic_model` default
> (`"qwen3.6-27b"`) on Apple Silicon — a gap found by tracing a real
> automation-pipeline candidate (Qwen3.6 MLX/GGUF quants) all the way into
> agentalloy's actual authoring config, rather than stopping at "this seems
> relevant."

> **Location note.** At runtime the SDD spec phase writes the spec to
> `docs/spec/authoring-critic-model-setup-docs.md`, git-ignored. This file
> is the committed, reviewable copy.

## Context

`src/agentalloy/config.py`'s `AuthoringConfig` already defaults
`critic_model` to `"qwen3.6-27b"` — the author-critic bulk-authoring
pipeline (`docs/operator.md`'s "Skill Authoring Pipeline" section) already
nominally expects Qwen3.6-27B for its QA/critic step
(`authoring/qa_gate.py`, invoked via `authoring/pipeline.py`'s
`qa_one(critic_model=ac.critic_model)`). This talks to a user-run LM
Studio server at `AUTHORING_LM_STUDIO_BASE_URL` (default
`http://localhost:11434`) — agentalloy does not download or manage this
model itself, unlike the embed/reranker GGUFs (`recommend-models`/
`pull-models`), which are fully automated.

**The real gap**: nothing in the repo — not `docs/operator.md`, not any
setup wizard step, not a README — tells a user which actual Hugging Face
repo/quant to load into LM Studio so that `/v1/models` reports something
matching `"qwen3.6-27b"`. `lm_client.py`'s `ensure_model_loaded()` will
raise a clear `LMModelNotLoaded` error at runtime if it's missing, so the
failure mode is loud, not silent — but there's no guidance for fixing it
before hitting that error.

This was found by chasing a real automation-pipeline `accept` verdict
(`manual-2026-07-12-qwen3.6-mlx-gguf-quants`, evaluated under the newly
widened "local-model fit" lens) all the way into the actual agentalloy
codebase, rather than stopping at "seems locally relevant." Real,
hardware-verified options exist for Apple Silicon specifically (Jay's own
48GB M4 Pro Mac Mini), from that same evaluation.

## Assumptions (correct these before design)

- **Documentation only, not a code or config change.** `critic_model`'s
  default value is already correct (`"qwen3.6-27b"`); this slice does not
  change it. There is no auto-download to build for the authoring
  pipeline's models — unlike the embed/reranker GGUFs, LM Studio itself is
  the download/serving mechanism, and building an automated puller for it
  is out of scope (see Out of Scope).
- **Apple Silicon only, in this pass.** The only hardware actually
  researched is Jay's M4 Pro Mac Mini (48GB unified memory). NVIDIA,
  AMD, and CPU-only guidance would require the same kind of real,
  hardware-grounded research this pass did for Apple Silicon — fabricating
  it now would violate this whole session's "prefer real verification"
  practice. Out of scope, named explicitly as a follow-up.
- **`critic_model` only, not `model`.** `AuthoringConfig.model` (default
  `"qwen3-14b-instruct"`, the author/revise step, a *different* local
  server at `AUTHORING_LM_BASE_URL`/`http://localhost:11435`) was not
  researched this pass. Out of scope — don't extend today's Qwen3.6
  research to cover a model it wasn't about.
- **Docs location**: extend `docs/operator.md`'s existing "Skill Authoring
  Pipeline" section (the only place the author-critic architecture is
  currently documented at all) rather than creating a new, disconnected
  doc file — design confirms this or proposes an alternative.

## What

**A new subsection under `docs/operator.md`'s "Skill Authoring Pipeline"**
(or design's chosen alternative location), documenting:

- The `AUTHORING_MODEL`/`AUTHORING_CRITIC_MODEL`/
  `AUTHORING_LM_STUDIO_BASE_URL`/`AUTHORING_LM_BASE_URL` env vars, their
  defaults, and which pipeline step (author/revise vs. QA/critic) each
  config value controls — currently undocumented anywhere.
- For the critic model on Apple Silicon specifically: real, linked
  Hugging Face repos for Qwen3.6-27B in both MLX (4-bit: 26.2GB, 8-bit:
  34.7GB) and GGUF (4-bit: ~18GB, via llama.cpp/Metal) formats, with a
  plain-language note on matching quant to available unified memory
  (leave headroom for macOS + LM Studio itself, not just the model file
  size).
- An explicit callout that this is Apple-Silicon-specific guidance, with
  NVIDIA/AMD/CPU-only guidance named as not-yet-written (not silently
  omitted).

**No code change.** No new CLI command, no new wizard step, no change to
`config.py`'s defaults (already correct) or any `install/subcommands/`
file.

## Acceptance Criteria

1. **The new docs section accurately describes the two-model split**
   (author model vs. critic model, their distinct default values and
   distinct LM Studio base URLs) — verifiable by direct comparison against
   `config.py`'s `AuthoringConfig` and `authoring/pipeline.py`'s actual
   usage.
2. **At least one real, currently-live Hugging Face repo link is given for
   each of MLX and GGUF quant formats of Qwen3.6-27B**, with accurate file
   sizes as found during this session's real research (26.2GB/34.7GB MLX,
   ~18GB GGUF) — verifiable by checking each link resolves to a real
   model page.
3. **The doc explicitly scopes itself to Apple Silicon** and names
   NVIDIA/AMD/CPU-only as future work, not silently absent — verifiable by
   direct reading.
4. **No code touched.** Zero diff outside `docs/`.
5. **Live proof**: after merge, `git diff main -- docs/operator.md`
   (or wherever design lands the section) reads correctly rendered as
   Markdown — verifiable by direct inspection, no build step exists for
   this doc that could silently corrupt it.

## Out of Scope

- **Building an automated puller for the authoring pipeline's models**
  (unlike `pull-models` for the embed/reranker GGUFs). LM Studio's own
  model browser already does this; scripting around it is a real,
  separate feature, not attempted here.
- **NVIDIA, AMD, or CPU-only hardware guidance.** Not researched this
  pass; naming it as absent (AC3) is honest, fabricating it is not.
- **The author model (`AuthoringConfig.model`, default
  `"qwen3-14b-instruct"`).** Not researched this pass; a separate,
  future candidate if pursued.
- **Changing `critic_model`'s default value or adding a preflight check
  for it.** The default is already correct; `ensure_model_loaded()`
  already provides a clear runtime error if it's missing. Neither needs
  touching.
- **Any change to the embed model / reranker stack**
  (`recommend-models`/`pull-models`) — a fully separate, already-automated
  subsystem, untouched by this slice.

## Design surface (hand-off to the design phase)

- **Exact doc location**: extend `docs/operator.md`'s existing section
  (assumption above) vs. a new dedicated file. Given `operator.md` is
  already the sole place this pipeline is documented, extending it is the
  default; design confirms or names a concrete reason to split it out.
- **How prescriptive to be about which specific quant to recommend as
  *the* default** (e.g. GGUF 4-bit for its smaller footprint and broader
  headroom, vs. presenting MLX/GGUF as equally-valid options) — a real
  editorial call design should make explicitly, not leave implicit.
