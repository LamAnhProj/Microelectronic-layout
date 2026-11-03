---
name: layout-verify
description: Plan and assess process-specific DRC, LVS and parasitic extraction using exact layout/netlist snapshots and verifiable reports.
---

1. Establish top cell, schematic netlist, layout hash, PDK/deck/model revisions,
   process options, tool versions and layer mapping.
2. Qualify the selected deck on a known-good and deliberately broken cell.
3. Run DRC and extraction using that process's documented supported commands.
4. Compare extracted and reference netlists with the supported Netgen LVS setup.
5. Check tool exit, report existence, expected devices/ports and actual violations.
6. Associate every report with its exact input hash. Missing evidence is unknown.
7. Pass extracted netlists to `circuit-simulate` for performance comparison.

Run `make qualify` for the tool scaffold: actual ngspice RC analysis, Magic startup,
Xschem version, Netgen matching/mismatching fixtures, synthetic KLayout width DRC,
and live editor bridge regression. Inspect its UUID `qualification.json` and logs.
The qualification uses synthetic geometry and ideal devices, not a PDK.
No foundry decks are installed/qualified yet; there is no universal `make verify`.
Read `knowledge/debug-and-evidence.md` and the chosen PDK's official documentation.
