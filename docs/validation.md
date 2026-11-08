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

## Second process circuit — GF180MCU D on Mac, 2026-11-07

Volare installed the `gf180mcu_fd_pr` primitive bundle at open-pdks revision
`c6d73a35f524070e85faff4a6a9eef49553ebc2b` beside SKY130A. It exposed
GF180MCU variants A/B/C/D and occupies about 2 GiB. The D variant was selected
for a 3.3 V CMOS inverter experiment in `examples/gf180_inverter/`. The run
`runs/gf180_inverter/5e088100-7b10-427d-9140-67ff56d4d8cb/report.json`
was produced on the actual macOS arm64 host and passes its stated open-PDK
checks. The dedicated runner hashes source files, model and rule trees, the
worker image, adapted native decks, and generated artifacts.

- Worker ngspice 44.2 used the vendor `design.ngspice` globals and
  `sm141064.ngspice` typical models. At 25 °C with a 5 fF load, the schematic
  simulated at 3.3 V high, 5.4 nV low, 33.25 ps falling and 34.35 ps rising
  delay. The first run without `design.ngspice` failed on undefined `fnoicor`.
- Worker Magic 8.3.686 loaded `gf180mcuD` and exported GDS without feedback.
  A routed layout using the 3.3 V NMOS/PMOS generators, manual gate contact,
  metal buses, and explicit substrate/well ties produced zero full-area DRC
  errors. The default generator gate contacts produced 10 errors, so the routed
  layout disables them and places a separate legal contact. A control with
  no gate contacts or wiring also produced zero DRC errors, illustrating that
  DRC alone does not establish connectivity. Magic printed two
  `Unknown cif layer` diagnostics (`ndiff_missing_pwell` and
  `mvndiff_missing_pwell`) while loading the full DRC style; their effect on
  check coverage needs investigation.
- Worker Netgen 1.5.327 loaded the pinned GF180 setup and uniquely matched the
  connected layout to the schematic: two devices and four nets. It rejected
  both the disconnected control and an intentionally wrong PFET bulk.
- Capacitance-extracted simulation gave 44.04 ps falling and 45.61 ps rising
  delay at the same corner/load, compared with 33.25 ps and 34.35 ps from the
  schematic. These are simulated values, not silicon measurements. The
  extraction includes device geometry and parasitic capacitance but not
  distributed wire resistance.
- Native macOS KLayout 0.30.12 ran the vendor full DRC deck with FEOL, BEOL,
  off-grid and connectivity checks against the routed GDS: zero report items.
  Its `metal1` table found 20 items on the default PCell control and zero on
  the disconnected control. The stock vendor runset failed on macOS because
  its Ruby logger calls Linux `pmap`; the runner replaced only that logger call
  with macOS `ps` in hashed run-local deck copies. Antenna and density tables
  were not run.

An exploratory call to the PDK's `gf180mcu::subcon_3p3_draw` helper used
unrecognized Magic layer names (`subdiffc`, `subdiff`). The routed layout paints
the valid substrate contact layers explicitly. The Magic unknown-CIF warnings
and native-runset adapter remain integration issues. Both PDKs are installed
for local learning, but neither is a foundry-qualified process package. R2
remains storage only; remote compute is unfinished.

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

## Distributed wire R-C extension on Mac, 2026-11-08

The pinned arm64 worker's Magic 8.3.686 now runs a separate detailed R-C
extraction on a private flattened copy of each connected inverter cell, using
[`examples/rcx.tcl`](../examples/rcx.tcl). The procedure follows the
[Magic 8.3 R-C extraction guide](https://www.opencircuitdesign.com/magic/howto.html):
`extract do unique`, `extract do resistance`, then `ext2spice extresist on`.
The minimum network-selection thresholds are zero and the resistor
simplification setting is 1 mΩ. The original GDS, LVS netlist and
capacitance-only PEX netlist are preserved. The R-C netlist and testbench are
hash-listed in each UUID report; all listed artifact hashes were verified.

| PDK and run | Explicit R / C | C-only tPHL / tPLH | R-C tPHL / tPLH | R-C increment |
| --- | ---: | ---: | ---: | ---: |
| SKY130A `61dff494-ef22-4cbb-a9c8-6d069f581a8f` | 42 / 20 | 24.91 / 30.26 ps | 27.67 / 34.93 ps | +2.76 / +4.67 ps |
| GF180MCU D `bb8567ef-7ea6-4385-af9d-965561489f87` | 11 / 13 | 44.04 / 45.61 ps | 44.93 / 46.86 ps | +0.89 / +1.24 ps |

Both full pipeline reports passed on the native arm64 Mac. Magic emitted
four extracted nets in each R-C run, the netlists contain positive explicit
resistors, ngspice passed the same logic and delay criteria, and all evidence
files match their SHA-256 manifests. Direct Netgen comparison against the
R-C netlist reports extra resistor devices, so the original resistor-free
extraction remains the LVS reference. A separate graph check collapses only
positive resistor edges and verifies that both MOS transistors retain the
expected four-port topology; short and wrong-terminal controls reject bad
netlists. The numerical differences combine the
wire resistance network and Magic's re-extracted capacitance from a flattened
cell; they do not isolate resistance alone. These results are open-PDK
engineering estimates. Antenna/density, foundry qualification and silicon
measurement remain open. GF180 Magic still emits unknown CIF layer warnings.

### Layout-linked R-C analysis

The Chip Lab layout overlay now maps all extracted R-C node anchors onto the
saved GDS coordinate frame. It derives the conversion from the four port boxes
in the hashed `layout.tcl` and the matching port rectangles in the flattened
`inverter.ext`, then verifies the `inverter.res.ext` nodes fall within the GDS
bounds. It also checks each SPICE resistor against Magic's resistance
annotation. The anchored links are electrical connections, not exact routed
shapes or a per-layer resistance map.

The branching resistor network gives these DC effective port-to-terminal
resistances: SKY130 IN to NMOS/PMOS gate 387.59/563.60 Ω and OUT to
NMOS/PMOS drain 90.08/120.26 Ω; GF180 IN to the gates 85.35/112.84 Ω and
OUT to the drains 10.56/8.29 Ω. VDD/VSS branches and device bulk paths are
also listed in the UI. These values characterize the extracted network at DC;
they are not isolated timing penalties. The R-C netlists contain 6.428 fF
(SKY130) and 5.811 fF (GF180) of top-level capacitors, including internal
nodes, so a simple C-only versus R-C timing subtraction does not isolate R.

### Shorter inverter layouts and waveform diagnosis, 2026-11-08

The original hashed runs above are the references. The only source change in
each revision is `layout.tcl`; the worker image, pinned PDK/model/deck hashes,
testbench, device sizes and extraction script match its reference. GF180's
PMOS, well tap and upper contacts moved 2 µm toward the NMOS, shortening the
continuous polysilicon gate. SKY130's PMOS moved 1 µm toward the NMOS and its
outer metal2 IN/OUT bus spines moved inward while retaining clearance from
the supply rails. These were geometry changes, not schematic substitutions.

| Process and revised Mac run | RC top-level C, before → after | IN→PMOS gate R, before → after | RC tPHL, before → after | RC tPLH, before → after |
| --- | ---: | ---: | ---: | ---: |
| SKY130A `a48fd805-e40e-467e-8076-395e6b3caaae` | 6.42764 → 6.21625 fF | 563.602 → 563.021 Ω | 27.6697 → 27.4270 ps | 34.9329 → 34.6056 ps |
| GF180MCU D `53c0cbd1-8b41-4346-a913-2c371ad8726e` | 5.81053 → 5.33810 fF | 112.8388 → 77.2290 Ω | 44.9314 → 44.2421 ps | 46.8556 → 45.9978 ps |

Both revised runs passed Magic full DRC, native KLayout full DRC with zero
items, unique two-device/four-net Netgen LVS, topology-checked detailed R-C
extraction and ngspice delay/logic acceptance. The Mac dashboard reruns the
three transient decks with native ngspice and measures 50% delay plus 90–10%
fall and 10–90% rise slew from the trace samples. Its analysis endpoint
checks the trace delays against each run's hashed measurements.

The largest extracted capacitor pairs in the original layouts are VDD–VSS,
IN–VSS and OUT–VSS. The first is supply coupling, not a direct output load.
The output also sees the common external 5 fF testbench load. In GF180 the
shorter poly gate reduced both IN-associated extracted capacitance (1.78235
to 1.49413 fF) and PMOS gate access resistance. In SKY130 the metal2 area
reduction lowered total extracted capacitance, but the PMOS gate path stayed
near 563 Ω, so the timing improvement was modest. These correlations support
the geometry change; the extraction data does not attribute each capacitor
or resistor to a unique shape or conductor layer. The change from C-only to
R-C simulation also includes flattening-related capacitance changes, so it
cannot be labeled a resistance-only delay penalty. These remain nominal
open-PDK simulations, not silicon measurements or foundry signoff.

### Separate fast layout variants, 2026-11-08

`examples/sky130_inverter/layout_fast.tcl` and
`examples/gf180_inverter/layout_fast.tcl` preserve the prior validated
`layout.tcl` files. Run either with `python3 examples/sky130_inverter/run.py fast`
or `python3 examples/gf180_inverter/run.py fast`. Each runner copies the chosen
source into its private UUID run as `layout.tcl`, records the variant and
source hash, and executes the same DRC, LVS, extraction and simulation checks.

| Process and fast Mac run | R-C C, prior → fast | IN→PMOS gate R, prior → fast | R-C tPHL, prior → fast | R-C tPLH, prior → fast |
| --- | ---: | ---: | ---: | ---: |
| SKY130A `131db9e7-f6f9-46c2-a293-3b3c0d55eda7` | 6.21625 → 6.07672 fF | 563.021 → 562.708 Ω | 27.4270 → 27.2181 ps | 34.6056 → 34.3251 ps |
| GF180MCU D `d77486cf-979a-4b53-9ac2-72b975d43ae2` | 5.33810 → 5.16147 fF | 77.2290 → 50.5217 Ω | 44.2421 → 43.8085 ps | 45.9978 → 45.4324 ps |

The fast GF180 variant brings PMOS another 1.5 µm toward NMOS, reducing the
shared poly gate length. The fast SKY130 variant brings PMOS another 0.8 µm
closer and pulls the OUT metal2 spine inward. Both pass Magic full DRC, native
KLayout full DRC with zero reported items, unique Netgen LVS, detailed R-C
topology checks, and transient acceptance on the Mac. Device sizes, model
corner, 25 °C temperature, 5 fF load and input pulse remain fixed. The SKY130
gate resistance is still high; the measured speed gain there is small.

The PEX page also generates input-hashed DC and AC benches from the selected
extracted netlist. DC sweeps VIN from 0 to the nominal supply in 10 mV
(SKY130) or 20 mV (GF180) steps and interpolates the VOUT=VIN trip point.
AC linearizes at that measured trip point with a 1 V small-signal source,
40 points per decade from 1 kHz to 100 GHz, and the same 5 fF load. It
reports gain and phase at 1 kHz and an interpolated −3 dB bandwidth. These
R-C exploratory measurements provide a second performance check:

| Process | DC trip, prior → fast | AC −3 dB bandwidth, prior → fast |
| --- | ---: | ---: |
| SKY130A | 0.868681 → 0.868682 V | 575.718 → 582.445 MHz |
| GF180MCU D | 1.531854 → 1.531855 V | 334.246 → 337.605 MHz |

These DC/AC benches are exploratory Mac ngspice analyses, separate from the
validated transient pipeline. The exact generated decks, settings, output
hashes and plots are available in PEX. Small-signal gain at the switching
point does not describe large-signal logic gain across the full input range.
