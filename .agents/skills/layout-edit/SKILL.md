---
name: layout-edit
description: Plan reviewed custom-layout placement or routing edits with exact target checks and separate saving; validate scratch geometry tooling first.
---

Current executable proof: `make layout-smoke` writes and reopens a synthetic
scratch GDS in a new UUID directory. It does not edit an existing design or
demonstrate process correctness. No production editing command exists yet.

Future adapter contract:
1. Inspect file/editor target, lib/cell/view mapping, input hash, units and grid.
2. Generate a UUID proposal with bounded parameters and explicit layer mapping.
3. Review edit intent (`--approve-edit`); validate again at execution time.
4. Invoke prefixed `agentBridge...` procedures and collect before/after evidence.
5. Inspect unsaved results. Saving is a distinct job (`--confirm-save`).
6. Run layout verification on the saved snapshot. Inspect state before retrying
   any timeout. Start new operations on scratch cells.

Read `docs/architecture.md`. Do not claim the live bridge or guarded edits are
available until implemented and tested.
