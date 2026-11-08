# Working with the schematic, KLayout, DRC, LVS and PEX

Open the local dashboard at <http://127.0.0.1:8765>. Select **SKY130A** or
**GF180MCU D**, then select a passed Mac run. The run selector identifies a
specific UUID; its report records `Darwin`/`arm64`, source hashes, PDK revision
and tool evidence. Earlier cloud tests are separate evidence.

## Schematic editor

The source schematics are
[`examples/sky130_inverter/inverter.sch`](../examples/sky130_inverter/inverter.sch)
and [`examples/gf180_inverter/inverter.sch`](../examples/gf180_inverter/inverter.sch).
The dashboard's **Schematic** view renders their actual PDK device symbols by
default. It generates and displays a SPICE netlist using Xschem 3.4.4 in the
offline Docker worker. The two transistor connections and dimensions were
checked against the existing inverter references.

Native Xschem 3.4.4 is installed at
`/Users/auslyn/.local/xschem-3.4.4/bin/xschem`, with an `xschem` link in
`/opt/homebrew/bin`. XQuartz 2.8.6 and an X11-linked Tcl/Tk 8.6.18 build are
installed. The native CLI successfully generated netlists for both PDK source
schematics. Start XQuartz if needed, then use **Open native Xschem** to edit
the selected `.sch` with its PDK symbols. Save in Xschem and choose **Refresh**
in the dashboard to render and netlist the updated source.

The current full validation runners still use their pinned `inverter.spice`
inputs. Edits to `.sch` do **not** silently alter a validated run, layout or
LVS result. The dashboard labels the Xschem file as an editable source and the
SPICE evidence as a separate validated snapshot. **Simulate editor source**
netlists the current `.sch` and runs an exploratory nominal ngspice transient;
its waveform and hashes are saved under `runs/dashboard/editor_runs/`. This
action does not rerun layout, DRC, LVS or extraction.

The native Mac Xschem CLI was also checked independently of Docker for both
PDKs. Its generated netlists ran with native ngspice 47 and the local PDK
models, producing 6,044 transient samples per process. At 0.5 ns the low
input gave a high output; at 2 ns the high input gave a low output; at 4 ns
the output returned high. The local check files are under
`runs/dashboard/native-xschem/` and `runs/dashboard/native-ngspice/`; each
native ngspice directory has a `report.json` with source, deck, model entry
point and waveform hashes. These are exploratory 25 °C, nominal supply, 5 fF
tests, separate from the hashed full pipeline runs.

## Pipeline, waveforms and testbenches

Click any **Pipeline checkpoint** on the home page to inspect its measured
status, source or report files and recorded SHA-256 hashes. The popup can read
text evidence or open the related view. In **Waveforms**, the V(IN) and V(OUT)
checkboxes control each trace independently. Select **C only** or **Wire R-C**
to compare the two extracted simulations and their testbenches below the plot.

The pinned schematic testbench is `inverter.spice` in each selected run. The
capacitance-only testbench is `postlayout.spice` for SKY130 and
`connected/postlayout.spice` for GF180. The R-C testbench is
`rcx/postlayout_rcx.spice` or `connected/rcx/postlayout_rcx.spice`.
The **Testbench used for this run**
panel gives the exact local path and deck text. The post-layout deck retains
the input pulse, supply, 5 fF load, temperature and model corner, includes
the selected extracted inverter subcircuit, and substitutes an `XINV` instance
for the two schematic devices. The original run deck uses worker mount paths; the dashboard writes
a Mac-local adapted trace deck under `runs/dashboard/traces/` when it displays
a waveform. These trace replays are exploratory views of the pinned evidence;
the full pipeline runner remains the validated measurement source.

In **Layout**, select a run with R-C extraction to see the colored resistor
links over its GDS. Use **Net** to isolate IN, OUT, VDD or VSS; toggle resistor
links or capacitor anchors, then click an element in its list or on the canvas
to highlight its two Magic node coordinates and extracted value. The table
computes DC effective resistance from each external port to the MOS terminals
through the branching resistor network. The positions come from the run's
hashed `inverter.res.ext` node annotations, aligned with the hashed
`layout.tcl` port boxes and checked against the GDS bounds. Magic does not
identify an exact routed path or conductor layer for each resistor; straight
links in the overlay are electrical connections between node anchors.

## DRC errors in the GUI

In **DRC / LVS**, choose a layout variant in the **DRC marker browser**. The
connected layout passes; for a visible failure example choose **GF180 Default
PCell**. Its 20 KLayout metal1 marker items appear beside the corresponding
GDS. Click an item to zoom to its coordinates. **Open in KLayout** launches the
native Mac application with the GDS, PDK layer colors and the exact `.lyrdb`
report. The [KLayout marker browser](https://www.klayout.de/doc/manual/marker_browser.html)
can navigate each rule and geometry. KLayout's command-line `-m` option loads
the report database with the layout; the dashboard uses that supported path.

The SKY130 connected KLayout report and GF180 connected report both have zero
items. The SKY130 deliberate Magic DRC failure is recorded in its log, without
a KLayout marker location. Zero items means that specific deck and layout
passed; it does not imply foundry signoff.

## LVS comparison

The **LVS comparison** selector displays the Netgen schematic-versus-extracted
device and net counts, mismatch lines, and the complete Netgen report. For
GF180, the disconnected probe is DRC clean but has four schematic nets versus
seven extracted nets. The wrong-bulk comparison also fails. The passing
connected layout has two devices, four nets, and a unique match.

These are **Netgen** reports. They are not KLayout `.lvsdb` files, so the
dashboard does not pretend to open them in KLayout's native LVS browser. The
structured comparison and full text are the GUI for the actual Netgen result.

## PEX

The **PEX** view switches between `inverter_pex.spice` (capacitance only) and
`rcx/inverter_rcx.spice` (distributed wire R-C; under `connected/` for GF180).
It shows the top-level capacitors or resistor segments and their node pairs,
and compares each delay against the same schematic testbench. The full
extracted SPICE is visible and copyable. Magic flattens a private copy of the
connected cell for R-C extraction; original LVS and GDS evidence stay intact.
The R-C result is open-PDK engineering evidence, not foundry signoff.

For the revised inverter layouts, select the newest passed run in each
process. The **Waveforms** analysis measures the first complete transition
from the recorded native Mac ngspice traces and lists both 50% delays and
output slew. The **Layout** analysis explains the large IN gate paths and
capacitor net pairs below the GDS overlay. The **PEX** analysis repeats the
measured delay comparison next to the extracted element lists. When the
reference Mac run is present and all non-layout source, PDK and worker hashes
match, each panel shows the measured change after the geometry edit. Use the
run selector to inspect the original run directly. An extracted node link is
not a physical wire route, and the C-only/R-C difference is not a pure
resistance-only result.

The run selector labels the new `fast` variants. The previous `layout.tcl`
sources remain in the repository; `layout_fast.tcl` is a separate geometry
source in each process example. In **PEX**, first select C-only or R-C,
then choose Transient, DC transfer or AC small signal in **Testbench and
analysis**. Settings, results, a plot and the exact deck appear together.
Transient is validated pipeline evidence. DC and AC are separate exploratory
native Mac simulations on the selected extracted netlist. AC uses the
interpolated DC VOUT=VIN switching point as its bias. Inspect the deck before
interpreting gain or bandwidth, because the inverter is nonlinear outside
that small-signal operating point.

## Spectre

No Cadence Spectre executable or license configuration was found on this Mac.
Spectre is a separate licensed simulator; the current Volare PDK subsets and
testbenches are validated here with ngspice 47. It is the working SPICE
simulator for both PDKs. Cadence's [University
Program](https://www.cadence.com/en_US/home/company/cadence-academic-network/university-program.html)
offers institutional access to custom IC tools; its advertised self-service
free licenses for AWR and OrCAD do not establish free Spectre access. A Spectre
run needs licensed Cadence access, an appropriate host, compatible model
files, and a separately validated testbench. A SPICE-like file should not be
relabeled as a Spectre result without executing that flow.
