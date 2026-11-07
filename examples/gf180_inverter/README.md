# GF180MCU D inverter diagnostic

This is a 3.3 V, two-transistor inverter at the typical model corner and 25 °C.
The NMOS is 1/0.28 µm, the PMOS is 2/0.28 µm, and the testbench has a 5 fF
load. `inverter.spice` includes both the GF180 global parameter file and model
library. The expected behavior is logic inversion with each 50% delay under
1 ns. The measured Mac/arm64-worker values are in `docs/validation.md`.

The physical files are **diagnostics, not a completed inverter layout**.
`bad_pcell.tcl` uses the default Magic 3.3 V transistor generators; it produces
10 Magic DRC errors and 20 native KLayout metal1 rule items. `layout.tcl`
disables both gate contacts and produces zero Magic DRC errors, but leaves the
devices disconnected. Netgen correctly rejects its extracted netlist against
`schematic.spice`. The `run.py` report status is therefore `partial`.

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
makes a run-local copy of the `metal1` table and changes only the logger's
memory command to macOS `ps`. It hashes the original rule tree and adapted
runset. It has not run the full GF180 deck, antenna, density, a connected LVS,
or post-layout simulation. This open PDK is not foundry-qualified.
