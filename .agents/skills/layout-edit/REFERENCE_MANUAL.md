# Editor adapter contract

Exact usage and limits: `docs/bridge.md`. Shared architecture: `docs/architecture.md`.
Implementation: `src/chip_lab/bridge.py`; GUI entry point:
`bridge/start_klayout_bridge.py`; client: `scripts/layout_agent.py`.

The operation names are inspection/index, add-rectangle, save snapshot, and stop.
`agentBridgeCheckTarget`, `agentBridgeIndex`, `agentBridgeAddRectangle`, and
`agentBridgeSaveSnapshot` run inside the layout owner's thread. KLayout GUI mode
uses a Qt timer to pump requests; headless mode owns its own database.

The target includes session identity, path/hash, logical library/cell/view,
technology hash, DBU, revision and layout geometry/properties fingerprint.
It is a precondition, not a suggestion. Never edit by screen coordinates or use
an old target after manual changes. Batch operations inside the editor.

Job and result schemas are emitted by the implementation. They retain request
UUID, operation, target, parameters, status and outputs. Authentication is excluded
from those files. Use the report as evidence, and verify resulting geometry or
simulation independently. A saved snapshot is not a verified circuit.

`references/routing_guardrails.json` records current capabilities and
`references/execution_lessons.json` records tested operational lessons. Do not
interpret them as numerical PDK design rules.
