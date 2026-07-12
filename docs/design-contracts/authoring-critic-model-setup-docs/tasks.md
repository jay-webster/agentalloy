# authoring-critic-model-setup-docs — Tasks

## Tasks

1. **Add the `#### Local Model Setup (Author & Critic)` subsection to
   `docs/operator.md`.** Per approach.md §1-3: the env var table, the
   two-server distinction, and the Apple Silicon quant guidance with real
   links. Single self-contained task — one file, one new subsection.
   Satisfies AC1, AC2, AC3.

2. **Scope check + link verification.** Confirm `git diff --stat` shows
   only `docs/operator.md`; confirm each of the three Hugging Face links
   in the new subsection resolves to a real, live model page. Depends on
   Task 1. Satisfies AC4, AC5.
