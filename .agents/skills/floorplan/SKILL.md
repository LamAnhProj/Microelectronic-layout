---
name: floorplan
description: Plan analog or mixed-signal block placement before detailed layout, recording the engineer's placement method, constraints, tradeoffs and evidence. Use for the RCO or later circuits when choosing relative positions, dimensions and routing priorities.
---

# Floorplanning with the engineer

Use this skill to turn the engineer's step-by-step layout method into a reviewable floorplan. Record a rule only after the engineer supplies it or an exact PDK source supports it. Keep a running decision log with the choice, physical reason, expected electrical effect, alternatives considered, and evidence needed to test it. Ask for the next missing decision when it changes placement materially.

For this lab, start with the current circuit specification and schematic, then identify the actual device inventory, pin and power domains, critical and sensitive nets, device dimensions, and process-specific spacing or matching constraints. Make a separate plan for SKY130A and GF180MCU D; do not transplant dimensions or rules between them. Estimate block areas and wire lengths with units, and label estimates as estimates.

Produce a placement view showing block outlines, relative positions, orientation, pin locations, power paths, and intended routing corridors. Explain how each choice affects delay, coupling, matching, supply drop, substrate noise, or trim behavior. Record any tradeoff between shorter critical connections and a larger, easier-to-route floorplan. Keep the instructor's stated method distinct from the agent's proposals.

Before editing geometry, use `layout-inspect` to bind the target file, cell, PDK revision, grid, and source hash. Use `layout-edit` for guarded changes and a separate saved snapshot. Run `layout-verify` on that snapshot; treat an unrouted placement as placement evidence only, never as a connected circuit or LVS/PEX pass. Compare extracted behavior with `circuit-simulate` only after routing and extraction exist. Preserve decisions and failures with `lab-record`.

The initial RCO placement in `runs/rco/placement/` is a device placement experiment. Its DRC result does not establish routing, connectivity, LVS, PEX, or post-layout frequency. Review `examples/rco/README.md` for the actual topology and the selected PDK before extending it.
