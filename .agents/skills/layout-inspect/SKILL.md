---
name: layout-inspect
description: Read a GDS or OASIS file's hierarchy, layers, units and top cells without changing it; establish the exact target before layout work.
---

1. Identify the file and expected top cell, process and units.
2. Run `uv run --frozen --extra layout chip-lab inspect PATH`.
3. Check the returned SHA256, database units, top cells and layer inventory.
4. Resolve layer/datatype meanings against the exact process mapping.
5. Distinguish geometry inventory from connectivity or verified device identity.

For a live session, run `chip-lab bridge inspect --session SESSION` instead.
Use its target JSON with `chip-lab bridge index --session SESSION --target-file JSON`.
The editor performs the hierarchy fingerprint and layer counts locally; remote
object handles are not exposed. Wrong active cells/views and external file changes
are refused. See `docs/bridge.md` and `knowledge/layout-judgment.md`.
Do not infer nets from names alone.
