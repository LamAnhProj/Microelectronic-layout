# Working KLayout bridge

There are two modes sharing the same guarded operations:
- Headless: a project Python process owns a layout loaded from a saved file.
- GUI: a KLayout macro owns the active cellview; a Qt timer performs all database
  calls on the editor thread. The socket thread never touches layout objects.

The transport is a host-local Unix socket in a private temporary directory.
Authentication is stored in a separate mode-0600 file. Token values are never
written to jobs/reports. There is one socket client at a time; bounded requests
expire before execution if queued too long. There is no eval or shell operation.

## Open a scratch layout

Run `make layout-smoke` and take the printed GDS path. To attach the GUI:

```sh
bash scripts/start-klayout-bridge.sh /absolute/path/to/scratch.gds SCRATCH
```

Keep that terminal and editor open. Dismiss any normal first-start KLayout tips.
The terminal prints a session descriptor path. For headless mode instead:

```sh
uv run --frozen --extra layout chip-lab bridge serve \
  --layout /absolute/path/to/scratch.gds --cell SCRATCH
```

## Inspect, edit, save separately

In a second terminal in the repository:

```sh
LAB_SESSION=/absolute/path/to/session.json
mkdir -p runs/client
uv run --frozen --extra layout python scripts/layout_agent.py inspect \
  --session "$LAB_SESSION" > runs/client/before.json

uv run --frozen --extra layout python scripts/layout_agent.py add-rectangle \
  --session "$LAB_SESSION" --target-file runs/client/before.json \
  --layer M1/drawing --box-um 2 0 3 2 --approve-edit > runs/client/after.json

uv run --frozen --extra layout python scripts/layout_agent.py save \
  --session "$LAB_SESSION" --target-file runs/client/after.json --confirm-save

uv run --frozen --extra layout python scripts/layout_agent.py stop --session "$LAB_SESSION"
```

`chip-lab bridge ...` and `python scripts/layout_agent.py ...` are equivalent.
The target binds session ID, source path/hash, logical library/cell/view, process
profile hash, units, revision, and hierarchy/geometry/properties fingerprint.
Manual editor changes invalidate old targets. Switching active views/cells or
changing the source file on disk is refused. Inspect again before a new edit.

Edits change only the in-memory database. `save` writes a new private GDS snapshot
inside the session directory, verifies it can be reopened, and reports its hash.
It does **not** overwrite the original or mark the GUI document as saved. Manual
GUI Save remains a separate user action outside this bridge's snapshot workflow.

Every accepted transport request gets private UUID job/report files. Identical
job IDs are deduplicated within the session, including failed jobs; reusing an ID
with changed content is refused. Do not automatically retry a timed-out mutation:
an operation already started may still finish. Inspect state and its report first.

The only initial technology profile is `config/technology-scratch.json`: synthetic
M1/drawing = 1/0 on a 1 nm grid. It is not a foundry PDK. You may supply a reviewed
process layer/grid profile with `LAB_BRIDGE_TECH` or `--technology`, but that does
not install models, qualified rule decks, PCells, extraction or connectivity.
The layout fingerprint scans the loaded hierarchy; begin with small cells.

Implementation: `src/chip_lab/bridge.py`, `bridge/start_klayout_bridge.py`, and
`scripts/layout_agent.py`. Test with `make test` and `make qualify`.
