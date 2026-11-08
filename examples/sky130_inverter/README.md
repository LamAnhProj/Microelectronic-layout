# SKY130A CMOS inverter experiment

Two 1.8 V transistors (`nfet_01v8` W/L 1/0.15 µm, `pfet_01v8`
2/0.15 µm) drive a 5 fF load. The SPICE stimulus is a 1.8 V pulse with
20 ps edges and a 4 ns period. The stated corner is TT at 25 °C. Acceptance
limits are output high at least 1.7 V, low under 0.1 V, and both 50% crossing
delays under 100 ps. The baseline prediction is logic inversion and delays
within that bound; measured values are recorded separately.

The reference is [`schematic.spice`](schematic.spice). The deterministic
[`layout.tcl`](layout.tcl) uses the pinned SKY130A Magic generators, makes
physical source and bulk ties, and writes GDS plus LVS and capacitance-only
extraction netlists. The shared [`rcx.tcl`](../rcx.tcl) flattens a private copy
of the saved layout, extracts explicit wire resistors, and writes a separate
R-C netlist. [`run.py`](run.py) executes the worker checks, native Mac
KLayout DRC, and deliberate DRC/LVS failures. It keeps UUID run reports under
ignored `runs/sky130_inverter/`.

On the Mac, install the pinned primitive subset once:

```sh
uvx --from volare volare fetch --pdk-root "$PWD/pdks/volare" --pdk sky130 -l sky130_fd_pr c6d73a35f524070e85faff4a6a9eef49553ebc2b
uvx --from volare volare enable --pdk-root "$PWD/pdks/volare" --pdk sky130 -l sky130_fd_pr c6d73a35f524070e85faff4a6a9eef49553ebc2b
docker compose build --quiet worker
python3 examples/sky130_inverter/run.py
```

The PDK is from [Volare](https://github.com/chipfoundry/volare), which packages
[open_pdks](https://github.com/fossi-foundation/open-pdks). The PDK install is
ignored by Git and mounted read-only in the offline worker. The runner records
aggregate hashes of the active Magic, Netgen, ngspice and KLayout deck/model
trees, because the generic circuit manifest copies only declared source files.

The post-layout comparison includes both capacitance-only and distributed
wire R-C networks. The R-C run uses zero selection thresholds and a 1 mΩ
minimum resistor simplification setting; the accepted netlist must contain
explicit positive resistors and pass ngspice measurements. It does not
establish foundry-qualified parasitics or silicon performance. See
[`docs/validation.md`](../../docs/validation.md) for the run and observed gaps.
