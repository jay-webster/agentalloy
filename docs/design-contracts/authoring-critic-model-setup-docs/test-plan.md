# authoring-critic-model-setup-docs — Test Plan

## Test Cases

No code, no unit tests apply. Verification is direct inspection.

### Task 1 — new subsection

- **T1.1 (AC1).** Direct comparison: the table's four env vars, their
  defaults, and which pipeline step each controls match
  `AuthoringConfig` in `config.py` and the actual `ac.model`/
  `ac.critic_model`/`ac.lm_base_url`/`ac.lm_studio_base_url` usage in
  `authoring/pipeline.py`, `authoring/driver.py`, `authoring/__main__.py`
  exactly.
- **T1.2 (AC3).** Direct reading: the subsection states it's Apple-Silicon-
  specific and names NVIDIA/AMD/CPU as not-yet-written, rather than
  presenting Apple Silicon guidance as if it were universal.

### Task 2 — scope check + link verification

- **T2.1 (AC4).** `git diff --stat main` shows only `docs/operator.md`.
- **T2.2 (AC2).** Each of the three Hugging Face URLs in the new
  subsection fetched and confirmed to resolve to a real model page
  matching the stated format/size.
- **T2.3 (AC5).** The rendered Markdown (table syntax, link syntax) reads
  correctly — visual inspection of the diff, no malformed table rows or
  broken link syntax.
