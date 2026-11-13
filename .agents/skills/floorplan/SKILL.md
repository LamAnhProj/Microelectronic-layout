---
name: floorplan
description: Floorplan analog or mixed-signal circuits before detailed layout. Use when choosing RCO or other circuit block positions, dimensions, orientations, pins, and routing priorities.
---

# Floorplanning with the engineer

Turn the engineer's step-by-step method into a reviewable floorplan. Annotate each session in `knowledge/lab-book.md` before distilling a reusable rule. Read [taught concepts](references/concepts.md) when applying an engineer-taught principle; each entry gives its physical cause, conditions, exceptions, and observable test. Link a process-specific reference only when that process actually needs different guidance. Do not promote an agent proposal to an engineer-taught rule.

## Decision path

1. Read the current circuit specification and schematic. Inventory devices, pins, supply domains, critical and sensitive nets, dimensions, and constraints. Mark unknowns.
2. If the PDK changes, make a separate plan and resolve dimensions, grid, and spacing against that exact PDK. Never transplant numerical rules from SKY130A to GF180MCU D or vice versa.
3. If an instructor rule applies, record its physical reason and use it. If its conditions are unclear, ask before making a consequential placement choice. If the agent proposes a choice, label the assumption and prediction.
4. Draw block outlines, relative positions, orientations, pins, power paths, and routing corridors. Estimate area and important wire lengths with units. Record each choice, expected effect, tradeoff, and test.
5. After each revision, compare predicted delay, coupling, matching, supply drop, substrate noise, and trim behavior with available evidence. Explain mismatches, change one meaningful choice, and repeat until the agreed placement criteria are met or the remaining gap is explicit.

Before editing geometry, use `layout-inspect` to bind the target file, cell, PDK revision, grid, and source hash. Use `layout-edit` for guarded changes and a separate saved snapshot. Run `layout-verify` on that snapshot. If it is unrouted, report placement and DRC evidence only; connectivity, LVS, PEX, and post-layout frequency remain unknown. Compare extracted behavior with `circuit-simulate` after routing and extraction exist. Preserve decisions and failed hypotheses with `lab-record`.

The initial RCO placement in `runs/rco/placement/` is a device placement experiment. Its DRC result does not establish routing, connectivity, LVS, PEX, or post-layout frequency. Review `examples/rco/README.md` for the actual topology and the selected PDK before extending it.
