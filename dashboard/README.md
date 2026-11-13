# Chip Lab dashboard

Run on the actual Mac from this repository:

```sh
make dashboard
```

Open <http://127.0.0.1:8765>. The server binds only to loopback. It reads the
selected run's report and evidence artifacts, parses its GDS with the native
KLayout Python module, and uses native Mac ngspice for dashboard waveforms when
available. The Docker worker remains the fallback and runs the full pipeline.
It does not upload a design, PDK, report, or waveform.

On this Mac, a user LaunchAgent starts the dashboard at login and restarts it
if it exits. Its configuration is
`~/Library/LaunchAgents/com.lamanhproj.chiplab.dashboard.plist`, and its log is
`runs/dashboard/server.log`. Check it with
`launchctl print gui/$(id -u)/com.lamanhproj.chiplab.dashboard`.
To stop the background instance, run
`launchctl bootout gui/$(id -u)/com.lamanhproj.chiplab.dashboard`.
To start it again, run
`launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.lamanhproj.chiplab.dashboard.plist`.

The **Test circuit** view creates an exploratory inverter netlist and waveform
under `runs/dashboard/experiments/`. It does not certify DRC, LVS, extraction,
or timing. **Run full pipeline** invokes the selected process's existing pinned
runner and saves a new UUID run under `runs/sky130_inverter/` or
`runs/gf180_inverter/`. The dashboard distinguishes these from earlier cloud
tests by showing the Mac run report's `Darwin` and `arm64` host fields.

Click any home-page pipeline checkpoint to inspect its metrics, artifact hashes
and recorded files. The waveform view can show V(IN), V(OUT), both or neither.
It reruns ngspice from the selected run's schematic, capacitance-only, or
distributed wire R-C netlist and saves traces under `runs/dashboard/traces/`.
The testbench panel shows the selected UUID's exact SPICE deck for each mode.
Crossing delays are read from the validated report, rather than estimated from
the displayed sampled curve. The **Layout** view overlays Magic's R-C node
anchors and resistor/capacitor connections on the selected run's actual GDS.
Filter by net and select an element to highlight its endpoints. Its table
solves the branching resistor network for DC effective resistance from each
port to its MOS terminals. Straight links join electrical node anchors; they
are not reconstructed wire paths or layer assignments. For mask-level editing
and signoff review, open the GDS in native KLayout.

Analysis panels under Waveforms, Layout and PEX now measure 50% delay and
10–90%/90–10% output slew from the three native ngspice traces. They identify
the largest extracted capacitor pairs and compare revised layouts with their
hashed reference Mac runs only when the PDK, model, deck, worker and testbench
hashes agree. The extracted elements do not identify a unique conductor shape
or layer; capacitance-only versus R-C also changes the flattening topology.

The newest passed runs use separate `fast` layout sources for both PDKs;
the run selector shows the variant. On **PEX**, choose capacitance-only or
distributed R-C extraction, then choose **Transient**, **DC transfer**, or
**AC small signal**. The panel shows the exact SPICE deck, full settings,
measured results and a plot. Transient uses the validated run deck. DC and
AC use separate input-hashed exploratory ngspice benches against that run's
extracted netlist; AC is biased at the DC trip point. The 5 fF load and
selected PDK model corner are preserved.

The **Layout comparison** panel places the selected GDS beside an earlier
passed run, defaulting to the fast layout's recorded comparison run. Scroll
or drag either pane to zoom or pan both together. The layer checkboxes above
apply to both, and the highlight switch marks polygons found only in the
earlier snapshot (coral) or only in the selected one (green). Click a point
to inspect visible layer membership at the same coordinate in both GDS files.
The summary also compares validated R-C delays and extracted capacitance.
Polygon changes are geometric differences, not automatically DRC violations
or net changes. Each comparison requires matching PDK/rule, schematic,
testbench and extraction-script hashes and verifies both GDS artifact hashes.

The **Circuit** dropdown switches between the validated inverter pipeline and
the nine-bit RCO schematic prototype. The **Circuit library** page shows the
RCO topology, capacitor word, master PMOS/NMOS switch, 512 kHz target, saved
Mac ngspice waveform, exact hashed deck, and a step-by-step engineering
decision log. Select a saved run or enter a new 0–511 code and use **Run native
ngspice**. The process dropdown changes between SKY130A and GF180MCU D; the
GF180 oscillator supply is 3.3 V and its control inputs are 1.8 V. The RCO
offers ideal and PDK passive models and native Xschem source. Its device
placement is unrouted; connected-layout LVS, PEX, and post-layout frequency
checks remain open.

The RCO page links to the [floorplan comparison](http://127.0.0.1:8765/floorplans/).
Its five saved revisions include 18 editable one-stage bank panels across the
two PDKs. In the placement sandbox, choose a revision and panel, then click or
drag numbered MIM units between interior sites. **Start empty** turns it into
a 77-unit SKY130A or 61-unit GF180MCU D placement exercise with a live
remaining-device counter and progress bar. The perimeter dummy sites stay
fixed. Drafts are saved in browser local storage per panel, with undo, reset,
and a JSON download. The editor does not change GDS or verify electrical
connectivity, dummy ties, DRC, LVS, PEX, or post-layout frequency.

The same page has a **Four capacitors in series** checkpoint beneath the
placement sandbox. It reads the latest passing native-Mac coupon report for
each PDK, verifies the saved GDS hash and DRC/LVS status, and draws M4, MIM,
and M5 polygons directly from that GDS with layer toggles. It compares
schematic, capacitance PEX, and R-C extraction input capacitance and
step-drive delay. **Open GDS + DRC in KLayout** launches the saved GDS and
its marker database. These isolated chains have no bank switch, dummy ring,
or oscillator frequency result. SKY's small coupon resolved no wire resistor;
GF's resolved one. The full RCO remains unrouted.

The **DRC / LVS** view now parses KLayout marker coordinates and Netgen
comparisons, including GF180's deliberate failing controls. **PEX** displays
the capacitor network, explicit wire resistors, and full netlist for RC runs.
**Schematic** shows the
actual PDK symbols rendered from editable Xschem source and can launch native
Xschem. It can run a separate exploratory transient from that source. See
[the GUI workflow](../docs/gui-workflow.md) for
the exact tool boundaries and steps.

The current evidence covers schematic simulation, connected layout, Magic and
native KLayout DRC, Netgen LVS, capacitance-only extraction, and flattened-cell
distributed wire R-C extraction for the two inverter cells. It does not cover
antenna or density signoff, foundry qualification, or silicon measurement. R2 is storage;
remote compute remains unfinished.

The server uses Python's standard library and the repository's existing
`.venv` and Docker setup. A manually started `make dashboard` instance stops
with Ctrl-C; stop the LaunchAgent first to free port 8765. To use another port, run
`.venv/bin/python dashboard/server.py 8766`.
