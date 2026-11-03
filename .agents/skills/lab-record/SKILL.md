---
name: lab-record
description: Preserve reproducible circuit experiments, verification evidence, source provenance and reusable engineering lessons in Git and R2 manifests.
---

1. Record hypothesis, assumptions, predictions, tool/PDK versions, input hashes,
   measured outcomes and owner rationale; retain failures as well as successes.
2. Keep small sources and original lessons in Git; never commit secrets or bulk data.
3. For knowledge updates run `make index`, then search a known topic to verify it.
4. Register dataset/PDK candidates in `config/sources.json`. A candidate is not
   licensed-for-training, installed, validated or a fabrication-ready process.
5. Read `docs/storage-r2.md`. Preview with
   `bash scripts/archive-r2.sh runs chip-lab-r2:BUCKET`; add `--upload` only for
   an intended transfer. Do not delete local artifacts based on a dry run.
6. Keep dataset splits by family/source design. See `docs/learning-plan.md`.

No Jira, tickets, enterprise release process or external messaging is required.
