# authoring-critic-model-setup-docs — Design

## Approach

### 1. Location: a new subsection under the existing "Skill Authoring Pipeline"

**Decision (resolves the spec's first open design question).** Insert a
new `#### Local Model Setup (Author & Critic)` subsection immediately
after the existing `### Skill Authoring Pipeline` prose in
`docs/operator.md` (after the QA-contract-reference paragraph, before
`### Skill Override CLI`). This is the only place in the repo that
already documents this pipeline's architecture at all — extending it
keeps one canonical location rather than splitting the authoring
pipeline's docs across two files for no structural reason.

### 2. Env var table, matching the existing `### Environment Variables` table style exactly

**Decision.** Reuse the exact `| Variable | Purpose | Default |` table
format already used for the runtime env vars (line 313-323 of
`operator.md`), for the four `AUTHORING_*` vars:

| Variable | Purpose | Default |
|----------|---------|---------|
| `AUTHORING_MODEL` | Author/revise model (drafts and rewrites skill YAML) | `qwen3-14b-instruct` |
| `AUTHORING_CRITIC_MODEL` | QA/critic model (reviews drafts against the R1-R8 contract) | `qwen3.6-27b` |
| `AUTHORING_LM_BASE_URL` | LM server URL for the author/revise model | `http://localhost:11435` |
| `AUTHORING_LM_STUDIO_BASE_URL` | LM Studio URL for the critic model | `http://localhost:11434` |

The distinct base URLs matter and are easy to miss reading the code cold
(`authoring/pipeline.py` uses `ac.lm_studio_base_url` for the critic step
specifically, `authoring/driver.py`/`__main__.py` use `ac.lm_base_url` for
author/revise) — spelling this out in the table itself, not just prose,
is what actually prevents a user pointing both at the same server and
being confused when only one model loads correctly.

### 3. Apple Silicon quant guidance: GGUF 4-bit as the stated default recommendation, MLX as the alternative

**Decision (resolves the spec's second open design question).** Recommend
GGUF 4-bit (~18GB) as the default suggestion — smallest footprint, most
headroom on any real Apple Silicon config, and consistent with
agentalloy's existing embed/reranker stack already preferring GGUF via
llama.cpp-family servers. Present MLX 4-bit/8-bit as valid alternatives
for users who prefer Apple's own inference stack or want the accuracy
tradeoff of 8-bit, not as inferior options — this is a "here's a sensible
default, here are the real alternatives" framing, not "one true answer."

Concrete content (all links live, checked during this session's research):

```markdown
**Apple Silicon** (verified against a 48GB M4 Pro Mac Mini; NVIDIA/AMD/CPU
guidance not yet written):

Load one of these into LM Studio for the critic model
(`AUTHORING_CRITIC_MODEL=qwen3.6-27b`):

- **GGUF, 4-bit (~18GB, recommended default)**:
  [unsloth/Qwen3.6-27B-GGUF](https://huggingface.co/unsloth/Qwen3.6-27B-GGUF)
  — via llama.cpp with Metal acceleration.
- **MLX, 4-bit (26.2GB)**:
  [unsloth/Qwen3.6-27B-UD-MLX-4bit](https://huggingface.co/unsloth/Qwen3.6-27B-UD-MLX-4bit)
  — Apple's own inference stack.
- **MLX, 8-bit (34.7GB, higher accuracy, less headroom)**:
  [unsloth/Qwen3.6-27B-MLX-8bit](https://huggingface.co/unsloth/Qwen3.6-27B-MLX-8bit)

Leave headroom beyond the model file size for macOS + LM Studio itself —
don't allocate the model to the last few GB of unified memory.
```

### 4. No new doc file, no table of contents update needed

**Decision.** `operator.md` has no generated TOC to regenerate (confirmed
by inspection — headings are plain Markdown, no `[[TOC]]` marker or
generator script referencing this file). A new `####`-level subsection
under an existing `###` heading needs no cross-reference updates
elsewhere in the repo.
