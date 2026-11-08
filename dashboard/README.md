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

This session's server is already running in the background. If the URL opens,
there is no need to start a second copy. Its log and PID are in
`runs/dashboard/server.log` and `runs/dashboard/server.pid`. Stop that instance
with `kill "$(cat runs/dashboard/server.pid)"`.

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
the largest extracted capacitor pairs and compare revised layouts with the
original hashed Mac runs only when the PDK, model, deck, worker and testbench
hashes agree. The extracted elements do not identify a unique conductor shape
or layer; capacitance-only versus R-C also changes the flattening topology.

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
with Ctrl-C. To use another port, run
`.venv/bin/python dashboard/server.py 8766`.
