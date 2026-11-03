---
name: layout-edit
description: Apply guarded rectangle edits through the KLayout bridge with exact target checks, on-grid geometry, private job reports and separate snapshot saving.
---

Read `docs/bridge.md` for exact commands. Prefix local commands with
`uv run --frozen --extra layout`; `python scripts/layout_agent.py` is the compatible entry point.

1. Establish a session with `bash scripts/start-klayout-bridge.sh FILE CELL`, or
   `chip-lab bridge serve --layout FILE --cell CELL` for the headless owner.
2. Run `chip-lab bridge inspect --session SESSION` and retain the JSON target.
3. Review bounded intent. Use `chip-lab bridge add-rectangle --session SESSION
   --target-file BEFORE_JSON --layer M1/drawing --box-um X1 Y1 X2 Y2 --approve-edit`.
4. Read the new target/report and inspect the result. No disk save has occurred.
5. Separately save with `chip-lab bridge save --session SESSION --target-file
   AFTER_JSON --confirm-save`. This creates a new snapshot; the original is not overwritten.
6. Route the saved snapshot to process verification. Do not replay a timed-out
   edit: inspect current state and UUID reports first.

Session, hierarchy/properties fingerprint, file hash, exact cell/view and technology
hash are checked. Off-grid/nonfinite/unmapped geometry is refused. Start on scratch
cells (`make layout-smoke`). The initial layer profile is synthetic, not foundry
qualified. Device placement, vias and automatic routing are not yet implemented.
Load `REFERENCE_MANUAL.md` and `references/*.json` when implementing or diagnosing
an adapter; keep this operational entry point short.
