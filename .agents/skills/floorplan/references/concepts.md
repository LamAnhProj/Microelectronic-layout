# Engineer-taught floorplanning concepts

## FP-001 — Begin with shape, area, and signal flow

**Source:** Engineer teaching, 2026-11-12. Apply to the RCO and later die or
block floorplans. This is design guidance, not a PDK design rule or a verified
performance result.

**Principle:** On a real die, begin with shape and area. Assess signal flow and
the large circuit components. For a free-rein block intended for top-level
integration, prefer a square outline or orthogonal protrusions while pursuing
the best post-layout performance against the circuit specification.

**Physical interpretation to test:** Shape constrains where large components,
power entry, pins, and routing corridors can go. Signal-flow placement may
change wire length, parasitic R/C, coupling, and hence oscillator frequency,
power, and trim behavior. A square outline alone does not establish good
electrical performance. This interpretation is the agent's model; test it with
connected layout and extraction.

**Decision path:**

1. If a top-level boundary or area budget is given, record it before placement.
   Otherwise, inventory large components and estimate an initial block area,
   including room for power, routing, taps, and process spacing. Label the
   estimate and missing margins.
2. Trace the signal path and identify large or placement-sensitive blocks.
   Place and compare candidate outlines that remain square-like or use
   rectilinear orthogonal extensions where useful.
3. If the outline preference conflicts with a measured performance requirement,
   record the tradeoff and compare alternatives. No exception or ranking rule
   has yet been supplied by the engineer.
4. Repeat placement, routing, extraction, and simulation as evidence becomes
   available. Keep the current placement-only DRC result distinct from a
   post-layout performance result.

**Useful measurements:** For a geometry bounding box,
`W = xmax − xmin`, `H = ymax − ymin`, `A_bbox = W × H`, and
`aspect = max(W,H)/min(W,H)`. These describe occupied extent, not allocated
die area, cell utilization, or routed area. Compare candidate outlines using
actual routed wire lengths, DRC/LVS, extracted R/C, and post-layout waveforms.

**Current RCO baseline:** See the 2026-11-12 FP-001 entry in
`knowledge/lab-book.md`. Its nearly square GDS bounding boxes are from
unrouted PDK-device placements. A top-level boundary and routed performance
have not been established.
