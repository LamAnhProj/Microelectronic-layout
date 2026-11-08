# Working with the schematic, KLayout, DRC, LVS and PEX

Open the local dashboard at <http://127.0.0.1:8765>. Select **SKY130A** or
**GF180MCU D**, then select a passed Mac run. The run selector identifies a
specific UUID; its report records `Darwin`/`arm64`, source hashes, PDK revision
and tool evidence. Earlier cloud tests are separate evidence.

## Schematic editor

The source schematics are
[`examples/sky130_inverter/inverter.sch`](../examples/sky130_inverter/inverter.sch)
and [`examples/gf180_inverter/inverter.sch`](../examples/gf180_inverter/inverter.sch).
The dashboard's **Schematic → Xschem source** toggle renders their actual PDK
symbols. It generates and displays a SPICE netlist using Xschem 3.4.4 in the
offline Docker worker. The two transistor connections and dimensions were
checked against the existing inverter references.

Native Xschem is not installed on this Mac. XQuartz is also absent; the
attempted Homebrew installation stopped because the system package installer
requires an administrator password in an interactive Terminal. Once XQuartz
and a native Xschem build are installed, the dashboard's **Open native Xschem**
button can launch the selected `.sch` with the pinned PDK symbols. Until then,
the `.sch` files can be edited as source text and regenerated with **Refresh**.

The current full validation runners still use their pinned `inverter.spice`
inputs. Edits to `.sch` do **not** silently alter a validated run, layout or
LVS result. The dashboard labels the Xschem file as an editable source and the
SPICE evidence as a separate validated snapshot. **Simulate editor source**
netlists the current `.sch` and runs an exploratory nominal ngspice transient;
its waveform and hashes are saved under `runs/dashboard/editor_runs/`. This
action does not rerun layout, DRC, LVS or extraction.

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

The **PEX** view reads the extracted `inverter_pex.spice` from the selected
UUID run, shows top-level capacitors and their node pairs, and compares
post-layout delays against the schematic testbench. The full extracted SPICE
is visible and copyable. The result is Magic capacitance extraction. It has
no distributed wire resistance, so the displayed delay penalty is not a full
RC signoff estimate.

## Spectre

No Cadence Spectre executable or license configuration was found on this Mac.
Spectre is a separate licensed simulator; the current Volare PDK subsets and
testbenches are validated here with ngspice. A Spectre run needs licensed
Cadence access, an appropriate host, compatible model files, and a separately
validated testbench. A SPICE-like file should not be relabeled as a Spectre
result without executing that flow.
