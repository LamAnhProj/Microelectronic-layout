# Microelectronic layout lab

Personal custom IC layout, simulation, automation, and engineering knowledge.
This repository combines the existing Cadence utilities with a lightweight
open-source lab. Original files in `skill-cadence-scripts/`, `GDS-parser/`, and
`unix/` are preserved. The existing license remains in effect.

## Start on your Mac

For the complete Mac setup kit, run `bash scripts/setup-git-macos.sh` first to
restore the bundled Git history, authenticate and publish. See
[setup handoff](docs/CONTINUE-SETUP.md). A source ZIP alone has no `.git` history.

Clone this repository, open Terminal in its directory, then run:

```sh
bash scripts/bootstrap-macos.sh
```

The script requires [Homebrew](https://brew.sh) and installs native KLayout,
ngspice, Git, uv, and rclone. It creates a project Python environment with a
pinned KLayout geometry package, indexes local engineering notes, and runs an RC
simulation, scratch GDS round trip and headless bridge tests. Add `--with-worker`
to install Docker Desktop and build/check the full Linux toolchain. Complete any
Docker first-run setup on your Mac. Full PDKs, datasets and local models are not downloaded.

```sh
uv run --frozen --extra layout chip-lab doctor
uv run --frozen --extra layout chip-lab search 'matching parasitics'
uv run --frozen --extra layout chip-lab sources
make test
make smoke
make layout-smoke
```

Keep this checkout: the editable package reads examples, configuration, and notes
alongside its source. The PyPI KLayout package is a headless geometry API; the
separately installed macOS application provides the GUI.

## Where things run

| Laptop | Optional Linux worker | Cloudflare R2 |
|---|---|---|
| KLayout GUI, small ngspice runs, editor, Git, Python utilities, local search | Magic, Netgen LVS, Xschem, larger verification/simulation jobs | Datasets, permitted PDK archives, waveforms, run bundles |

R2 stores objects; it does not execute tools. Remote execution needs a compute
host. Docker Desktop uses a Linux VM on macOS and remains optional. The worker's
one-CPU/1-GiB ceiling is for small tests, not arbitrary designs.

See [macOS setup](docs/setup-macos.md), [architecture](docs/architecture.md),
[R2 storage](docs/storage-r2.md), and [learning plan](docs/learning-plan.md).
Use the [bridge guide](docs/bridge.md) and [agent workflow](docs/agent-workflow.md)
for the working editor connection and circuit runner.

## Implemented

- Environment inventory, including physical RAM and CPU architecture.
- A real PDK-free ngspice RC experiment checked against its analytic cutoff.
- Scratch GDS write/read validation and read-only layout inventory.
- Host-local GUI/headless bridge with target/fingerprint checks, guarded rectangle
  edits, separate snapshot saving and private UUID jobs/reports.
- Manifest-based circuit runs with input hashes and measured acceptance criteria.
- Local engineering-note search using SQLite FTS5, without embeddings or a GPU.
- Six agent procedures in `.agents/skills/`, also exposed in `.github/skills`.
- A restricted Docker worker and dry-run-first R2 archive script.
- A source registry for evaluating PDKs and circuit examples before bulk downloads.

`make qualify` exercises the actual Linux tools and live KLayout application.
The included geometry profile and DRC fixture are synthetic. Foundry PDK setup,
device generators, routing, and process-qualified DRC/LVS/PEX remain next milestones.
Existing `.il` files still require Virtuoso.
No Jira or ticketing is included.
Python read in gds format file and dump various information (list cell, layer, hierarchy ... )
