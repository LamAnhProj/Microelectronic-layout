# GF180MCU D inverter experiment

This is a 3.3 V, two-transistor inverter at the typical model corner and 25 °C.
The NMOS is 1/0.28 µm, the PMOS is 2/0.28 µm, and the testbench has a 5 fF
load. `inverter.spice` includes both the GF180 global parameter file and model
library. The expected behavior is logic inversion with each 50% delay under
1 ns. The measured Mac/arm64-worker values are in `docs/validation.md`.

`layout.tcl` makes a connected inverter with the Magic 3.3 V device generators,
manual gate routing, source and drain buses, and explicit substrate and well
ties. It disables the generators' built-in gate contacts because those contacts
violate metal rules in this pinned PDK. Magic full DRC and the native KLayout
full deck report zero errors; Netgen uniquely matches the two-device,
four-net schematic. Capacitance-only and distributed wire R-C ngspice runs
follow. The R-C extractor flattens a private copy with the shared
[`rcx.tcl`](../rcx.tcl); the connected layout and LVS netlist stay intact. The report
hashes sources, deck and model trees, the worker image, and outputs.

The negative controls expose two failure modes. `bad_pcell.tcl` uses the
default Magic gate contacts: 10 Magic DRC errors and 20 native KLayout metal1
rule items. `disconnected_probe.tcl` has no gate contacts or wiring: it passes
DRC but Netgen rejects its disconnected netlist. DRC alone cannot establish
circuit connectivity.

Install the pinned GF180 primitive library and run on the Mac:

```sh
uvx --from volare volare fetch --pdk-root "$PWD/pdks/volare" --pdk gf180mcu -l gf180mcu_fd_pr c6d73a35f524070e85faff4a6a9eef49553ebc2b
uvx --from volare volare enable --pdk-root "$PWD/pdks/volare" --pdk gf180mcu -l gf180mcu_fd_pr c6d73a35f524070e85faff4a6a9eef49553ebc2b
python3 examples/gf180_inverter/run.py
```

Volare exposes GF180MCU A, B, C and D from this install. The experiment pins D,
the five-metal variant with 1.1 µm top metal. The primitive install occupies
about 2 GiB locally. PDK data stays ignored by Git and is mounted read-only in
the offline Docker worker.

The GF180 vendor KLayout runset's Ruby logger calls Linux `pmap`. The runner
makes run-local copies of the `metal1` and full DRC decks and changes only the
logger's memory command to macOS `ps`. It hashes the original rule tree and
adapted decks. The full run covers FEOL, BEOL, off-grid and connectivity rules;
antenna and density were not run. Magic prints two unknown CIF layer warnings
while loading its DRC style. Their effect on Magic rule coverage remains
unresolved, so the independent KLayout full deck is mandatory here. The PEX
comparison now includes explicit wire resistors as well as capacitance. This
open PDK is not foundry-qualified.
