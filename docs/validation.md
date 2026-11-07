# Scaffold validation

## Mac validation — 2026-11-07

Run on the user's macOS 26.5.1 arm64 laptop (8 GiB RAM), separately from the
earlier Linux x86_64 cloud tests below. Git history from the setup bundle was
restored and normal-pushed to `LamAnhProj/Microelectronic-layout` master.

- Native Git 2.56.0, gh 2.103.3, uv 0.13.7, ngspice 47, rclone 1.76.0,
  KLayout application and Python geometry core 0.30.12. Python is pinned to
  3.13 in `.python-version` so the arm64 KLayout wheel is used.
- `make test`: 11/11 passed, including the live macOS Cocoa KLayout bridge.
  `make index`, search, scratch GDS round trip, and the manifest RC run passed.
  The RC measurement was 159158 Hz against 159154.943 Hz analytic.
- Docker Desktop 4.98.0 on Apple Silicon: VM 2 CPUs, 3 GiB RAM, 1 GiB swap,
  40 GiB disk ceiling. The Compose worker has a separate 1 CPU, 1 GiB limit.
  `make qualify`: 6/6 passed in the arm64 worker. Qualification report:
  `runs/34691144-89f9-4282-a6da-5006743df264/qualification.json`.
  Worker image ID: `sha256:1ae56b5ec50120056697355ee83a9775f8c82ea36059bc25810d8c6880c9d109`.
- Debian's arm64 `netgen-lvs` package lacked `tclnetgen.so` here. The worker
  now builds upstream Netgen revision `93dcda14d36349d0b0ca63168d3cbbab20fe2ece`
  (version 1.5.327) and checks for that library during the build.
- Homebrew's KLayout cask was disabled after a macOS Gatekeeper failure. The
  official arm64 Tahoe 0.30.12 DMG was checked against its published MD5 and
  installed directly. Its executable and live bridge tests pass; the app has
  only an ad hoc signature, so normal Finder launch can require user approval
  in macOS Privacy & Security.

Those initial setup checks were synthetic. The later SKY130A inverter run below
adds a transistor-level check; it is not foundry signoff.

## First transistor circuit — Mac and arm64 worker, 2026-11-07

The two-device SKY130A inverter in `examples/sky130_inverter/` uses a Volare
open-PDK installation pinned to `c6d73a35f524070e85faff4a6a9eef49553ebc2b`.
This is a local, ignored 214 MiB primitive-library subset; no PDK files are
committed. `python3 examples/sky130_inverter/run.py` produced the passing
report `runs/sky130_inverter/2844e3c3-807a-4ba6-8403-d880fa440043/report.json`
on the actual macOS arm64 host. The runner hashes its source, model trees,
process decks, worker image, and generated artifacts.

- Worker Magic 8.3.686 loads SKY130A 1.0.532-2-gc6d73a3. The Docker build
  argument was renamed from `MAGIC_REVISION` to `MAGIC_COMMIT_PIN`: the old name
  collided with Magic's build variable and falsely compiled the version as
  8.3.0, below the PDK's 8.3.411 requirement. `make qualify` was rerun after
  this image change and all six worker checks passed.
- Full-area Magic `drc(full)` with `drc catchup`: zero errors. A deliberately
  narrow metal shape yields one error. GDS export: zero feedback entries. The
  first via layout had eight GDS export errors even while an incorrectly scoped
  DRC query said zero; both checks are now mandatory.
- Netgen using the pinned SKY130A setup: unique LVS match, two devices and four
  nets. A deliberately wrong PFET bulk connection yields a mismatch. Netgen
  can exit zero for a mismatch, so the final report text is checked.
- Native macOS KLayout 0.30.12 ran the pinned SKY130A FEOL, BEOL and off-grid
  deck against the generated GDS: zero report items. This is Mac validation;
  Magic, Netgen and ngspice ran inside the arm64 Docker VM on that Mac.
- TT, 25 C, 1.8 V, 5 fF load: schematic simulation gave 19.60 ps falling and
  23.42 ps rising delay; capacitance-extracted simulation gave 24.91 ps and
  30.26 ps. These are simulations, not measured silicon or qualified timing.

The extraction used for the reported comparison includes parasitic capacitance
and device geometry but not distributed wire resistance. An exploratory Magic
RC run emitted `Cannot open file (UNNAMED).ext` and a SPICE3 netlist with an
invalid inline `**FLOATING` comment; forcing ngspice output made it simulate,
but this RC path is not promoted as qualified evidence. The generic
`run-circuit` manifest passed on the worker but correctly reports
`pdk_verified: false`, because it hashes declared netlists only. The dedicated
runner separately fingerprints the local model and deck trees.

This open-PDK circuit check does not qualify a foundry PDK, fabrication signoff,
an Xschem graphical schematic, a live KLayout edit of this cell, or a remote
compute path. R2 remains storage only.

## Second process diagnostic — GF180MCU D on Mac, 2026-11-07

Volare installed the `gf180mcu_fd_pr` primitive bundle at open-pdks revision
`c6d73a35f524070e85faff4a6a9eef49553ebc2b` beside SKY130A. It exposed
GF180MCU variants A/B/C/D and occupies about 2 GiB. The D variant was selected
for a 3.3 V CMOS inverter experiment in `examples/gf180_inverter/`. The run
`runs/gf180_inverter/39b42ea0-fc40-44a0-969e-147910c30e03/report.json`
was produced on the actual macOS arm64 host and has status `partial`.

- Worker ngspice 44.2 used the vendor `design.ngspice` globals and
  `sm141064.ngspice` typical models. At 25 °C with a 5 fF load, the schematic
  simulated at 3.3 V high, 5.4 nV low, 33.25 ps falling and 34.35 ps rising
  delay. The first run without `design.ngspice` failed on undefined `fnoicor`.
- Worker Magic 8.3.686 loaded `gf180mcuD` and exported GDS without feedback.
  Its default 3.3 V NMOS/PMOS generators produced 10 full-area DRC errors.
  With both gate contacts disabled, the two PCells produced zero Magic errors,
  but the physical inverter remained disconnected. Magic also printed two
  `Unknown cif layer` diagnostics (`ndiff_missing_pwell` and
  `mvndiff_missing_pwell`) while loading the full DRC style; their effect on
  check coverage needs investigation.
- Worker Netgen 1.5.327 loaded the pinned GF180 setup and rejected that
  disconnected layout against the two-device inverter schematic: four nets
  versus seven connected nets plus one disconnected pin. This is an expected
  failure, not a passing LVS.
- Native macOS KLayout 0.30.12 ran the vendor `metal1` rule table against both
  generated GDS files. The disconnected probe had zero report items; the
  default PCells had 20. The stock vendor runset failed first because its Ruby
  logger calls Linux `pmap`; the diagnostic replaced only that logger call
  with macOS `ps` in a hashed, run-local deck copy. No complete GF180 DRC,
  antenna, or density pass has been obtained.

The GF180 stage has **no connected DRC-clean layout, passing LVS, extraction or
post-layout simulation**. A zero-error result on the disconnected probe cannot
be used as circuit validation. Both PDKs are installed for local learning, but
neither is a foundry-qualified process package. R2 remains storage only;
remote compute is unfinished.

The established SKY130A flow was rerun after the GF180 install and passed at
`runs/sky130_inverter/70ed6e90-de55-4b00-a0cb-92d9d5818ae1/report.json`.

## Earlier cloud validation — 2026-11-03

Tested on 2026-11-03 in the managed Linux x86_64 workspace, not on the Mac.

Host Python environment: KLayout core 0.30.12. Eleven tests discovered; nine pass
there and two require the worker's native executables. Those GUI/simulation
cases are exercised separately inside the worker, rather than claimed as passed
from a skipped host test.

The worker's six qualification checks pass:
1. Actual ngspice RC simulation: cutoff 159158 Hz versus analytic 159154.943 Hz,
   approximately 0.00192% error within the 1% threshold.
2. Pinned-source Magic starts headlessly and accepts Tcl commands.
3. Xschem version probe succeeds; interactive schematic operation is not tested.
4. Netgen distinguishes a matching generic circuit and an intentional mismatch.
5. KLayout's synthetic width DRC reports zero violations for the good fixture
   and one for the intentionally narrow rectangle.
6. KLayout application/Qt bridge: inspect, unsaved edit, separate snapshot save,
   original-file preservation, active-cell refusal and clean socket shutdown.
   The application uses hidden views (-z), not database-only batch mode (-zz).

Additional checks: stale hierarchy/properties fingerprints, wrong targets,
nonfinite/off-grid geometry, missing edit/save flags, duplicate job IDs, external
file changes, local socket authentication, private/exclusive reports, reference
search punctuation, and manifest circuit acceptance/rejection.

The packaged worker uses KLayout 0.30.0, ngspice 44.2, Netgen LVS 1.5.133, Xschem
3.4.4, and Magic source revision d914f66693e6ce0bd30dc1f2b265c2bcd7b20762.
It runs under the Compose restrictions: no runtime network, read-only root,
non-root user, dropped capabilities, one CPU, 1 GiB RAM, and a results mount.

SQLite indexes three original teaching notes. The scratch GDS round trip checks
one rectangle on synthetic layer 1/0, 1 nm DBU and 2 square micrometers area.
Shell syntax and Git whitespace checks pass. Run `make test` and `make qualify`
to reproduce checks and obtain local UUID reports.

Not tested/configured: macOS/Apple Silicon execution, Homebrew GUI installation,
R2 credentials/transfers, remote compute provisioning, foundry PDK models/decks,
PCells, automatic routing, process-specific DRC/LVS/PEX or fabrication acceptance.
