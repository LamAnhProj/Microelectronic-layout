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

The worker installs tools only. No PDK/decks are installed or qualified yet; there
is no universal `make verify` command. Do not invent command-line/deck options.
Read `knowledge/debug-and-evidence.md` and the chosen PDK's official documentation.
