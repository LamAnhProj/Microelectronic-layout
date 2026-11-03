# Microelectronic layout lab

Personal custom IC layout, simulation, automation, and engineering knowledge.
This repository combines the existing Cadence utilities with a lightweight
open-source lab. Original files in `skill-cadence-scripts/`, `GDS-parser/`, and
`unix/` are preserved. The existing license remains in effect.

## Start on your Mac

Clone this repository, open Terminal in its directory, then run:

```sh
bash scripts/bootstrap-macos.sh
```

The script requires [Homebrew](https://brew.sh) and installs native KLayout,
ngspice, Git, uv, and rclone. It creates a project Python environment with a
pinned KLayout geometry package, indexes local engineering notes, and runs an RC
simulation and scratch GDS round trip. It does not install full PDKs, datasets,
Docker Desktop, a standalone VM, or a local language model.

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

## Implemented

- Environment inventory, including physical RAM and CPU architecture.
- A real PDK-free ngspice RC experiment checked against its analytic cutoff.
- Scratch GDS write/read validation and read-only layout inventory.
- Local engineering-note search using SQLite FTS5, without embeddings or a GPU.
- Six agent procedures in `.agents/skills/`, also exposed in `.github/skills`.
- A restricted Docker worker and dry-run-first R2 archive script.
- A source registry for evaluating PDKs and circuit examples before bulk downloads.

The live editor bridge, guarded production editing, process layer mapping, and
qualified DRC/LVS/PEX flow are next milestones, **not implemented or validated
by the bootstrap tests**. Existing `.il` files still require Virtuoso.
No Jira or ticketing is included.
Python read in gds format file and dump various information (list cell, layer, hierarchy ... )
