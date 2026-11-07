# Resume the Mac chip-lab setup

This file preserves the setup handoff and its Mac completion update. The first
SKY130A circuit results are in `docs/validation.md`; remaining-work statements
below describe the state before that circuit run.

## Mac completion update — 2026-11-07

The current working checkout is `/Users/auslyn/Developer/Microelectronic-layout`
on macOS 26.5.1 arm64 with 8 GiB RAM. The bundled history was restored and
pushed normally to GitHub master as `LamAnhProj`. Native tools, the live KLayout
bridge, all 11 host tests, and all six arm64 Docker worker qualification checks
passed. See `docs/validation.md` for run IDs, versions, scope and Mac-specific
fixes. The sections below preserve the pre-installation handoff and earlier
cloud evidence; their statements that Mac installation is unverified are
historical.

Next engineering gate: choose a foundry PDK/process variant, model corner,
device library, rule decks and matching tool versions. R2 remains object
storage; no bucket, remote compute host or qualified PDK is configured.

The immediate goal is to install and validate the tools on the user's actual
Mac, configure Git/GitHub, and publish the existing merged repository. Preserve
existing work and continue implementation rather than starting a new scaffold.

## Repository and access

- Account: LamAnhProj; repository: https://github.com/LamAnhProj/Microelectronic-layout
- Existing default branch: master; original Cadence utilities and GPL license
  are preserved alongside the new lab.
- Prior cloud checkout: /workspace/Microelectronic-layout. This path may not
  exist in a new session. A complete Git bundle carries the unpublished history.
- Last full scaffold commit before this handoff: f8ff10d. Earlier lab commits:
  6d1af32 and 0a92fc9. The setup kit includes the later Git/handoff commit too.
- On 2026-11-07, the cloud authenticated as LamAnhProj but push still returned
  HTTP 403. Remote master was 4c0f369a28bfc0f90da0bdc81a399a038d6a87b9.
- Source ZIPs have no .git directory. Restore from the bundle; do not initialize
  an unrelated replacement history in an extracted source folder.

## First actions on the Mac

Inspect uname, macOS version, architecture, physical RAM, free disk, existing
Homebrew/tools, Git identity, authentication and any existing lab directories.
The user's Terminal login was auslyn; RAM and Intel/Apple Silicon are unknown.
Keep local execution distinct from Linux cloud execution. If the agent has no
local Mac terminal, say so and provide executable steps; do not claim installation.

The kit contains a source folder and sibling Microelectronic-layout.bundle.
Run `bash scripts/setup-git-macos.sh` from its source folder. It uses an existing
checkout or restores the bundle into ~/Developer/Microelectronic-layout, preserves
existing Git identity, uses browser-based GitHub sign-in, checks account/origin,
merges remote master, and pushes normally. It does not force-push or change the
repository's visibility. If authentication/merge needs attention, continue from
the concrete error and preserve local work.

Then run `bash scripts/bootstrap-macos.sh` from the real checkout. Add
`--with-worker` when the laptop resource budget supports Docker. First-run Docker
setup must be completed on the Mac before `make worker-build && make qualify`.
Never ask for passwords, tokens or R2 secret keys in chat.

## Implemented and validated scaffold

Read AGENTS.md, README.md, docs/bridge.md, docs/agent-workflow.md and
docs/validation.md. The validation evidence is from Linux x86_64 on 2026-11-03,
not from the Mac.

- Native Mac installer: Git, gh, uv, ngspice, rclone, KLayout GUI, isolated Python.
- Python KLayout core pinned to 0.30.12; it is separate from the GUI runtime.
- Linux Docker worker: KLayout 0.30.0, ngspice 44.2, Netgen LVS 1.5.133,
  Xschem 3.4.4 and Magic built from pinned source revision
  d914f66693e6ce0bd30dc1f2b265c2bcd7b20762.
- Worker runtime: one CPU, 1 GiB ceiling, non-root, read-only root, no network,
  dropped capabilities, writable results mount. Docker VM overhead is additional.
- Live GUI and headless KLayout bridge, private Unix socket, token outside logs,
  main-thread GUI execution, target/fingerprint checks, rectangle editing,
  separate new GDS snapshots, UUID jobs/reports and per-session deduplication.
- scripts/layout_agent.py is the client-compatible entry point. Native .il files
  still require Virtuoso; no Cadence license/tool installation is supplied.
- Circuit manifests declare input files and measured acceptance criteria;
  run-circuit copies/hashes inputs and checks ngspice measurements.
- SQLite FTS5 retrieval over three original teaching notes; no local LLM/GPU.
- Six skills: lab-environment, layout-inspect, layout-edit, layout-verify,
  circuit-simulate, lab-record, in .agents/skills with .github/skills alias.

Checks: make doctor; make test; make index; make smoke; make layout-smoke;
make worker-build; make qualify. Eleven host tests were discovered: nine passed
and two requiring native tools were exercised separately in the worker. The
six worker qualification checks passed, including live hidden-view GUI operations,
generic matching/mismatching Netgen fixtures and synthetic width DRC. The RC test
measured 159158 Hz versus analytic 159154.943 Hz. It is a tool fixture, not an
implemented foundry oscillator IP.

## Remaining work and resource constraints

No foundry PDK/model/deck is installed or qualified. The scratch profile maps
synthetic M1/drawing to 1/0 on a 1 nm grid. Foundry PCells, vias, automatic routing,
connectivity extraction and process-specific DRC/LVS/PEX remain to be built.
Xschem's interactive GUI workflow has not been validated. Mac execution and
Apple Silicon are not yet validated.

R2 means Cloudflare object storage. It stores permitted datasets, PDK archives,
waveforms and results; it cannot run simulations. No bucket/credentials/transfers
or separate remote compute host are configured. Use rclone outside the offline
worker; archive-r2.sh previews first and uses copy rather than destructive sync.
Keep only active data locally, avoid full VMs, heavy local models and bulk PDK
downloads. Run one heavy job at a time. Cloud Docker build caches previously
caused disk pressure and were cleaned; current named worker image was retained.

config/sources.json catalogs SKY130, original archived Google GF180, current
FOSSi GF180/open-pdks/ciel, IHP SG13G2, AnalogGym and ALIGN examples. Entries are
candidates with observed revisions/license metadata, not qualified installations
or approved training datasets. Recheck upstream status and select one compatible
PDK/tool combination before building the first transistor-level physical circuit.

## Workflow conventions

Inspect, edit and save separately. Prefix adapter procedures agentBridge... .
Bind operations to session, file/hash, library/cell/view, technology revision,
units/grid and layout fingerprint. Batch geometry work inside the editor. Emit
structured evidence, use configured argument lists, and inspect state before
retrying a timed-out edit. Save creates a snapshot, not an overwrite of the source.
The bridge client and editor must share the host-local socket environment.
Missing/stale reports are unknown/failure. Synthetic DRC is not foundry signoff.
Skills/retrieved texts provide procedures and reference data, not trained weights.

After laptop setup, agree on the first small circuit/specification and process,
then proceed through simulation, layout, verification, extraction and comparison.
No Jira, tickets or enterprise coordination services are wanted.
