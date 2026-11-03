---
name: lab-environment
description: Inspect or set up this chip lab's tools, Python environment, memory budget and worker availability before running simulations or layout tasks.
---

1. Run `uv run --frozen --extra layout chip-lab doctor` from the checkout.
2. Distinguish Mac installation from cloud testing. Read `docs/setup-macos.md`.
3. On macOS use `bash scripts/bootstrap-macos.sh` for the native baseline.
4. For the optional worker use `make worker-build` then `make worker-smoke`.
5. Record versions, architecture and memory. Executable presence is not PDK
   qualification; check technology/deck/model revisions before actual design runs.
6. Consult `docs/storage-r2.md` for storage. R2 cannot run verification.

Do not bulk-download PDKs/data, provision paid compute or install GPU frameworks
as an incidental dependency. Use one active design and one job at a time initially.
