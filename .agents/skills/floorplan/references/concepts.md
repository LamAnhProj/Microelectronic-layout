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

## FP-002 — Place the critical trim capacitor banks first

**Source:** Engineer teaching and correction, 2026-11-12. The existing
unrouted placement's square bbox is insufficient. Place capacitor banks
according to circuit function before arranging less critical components.

**Physical cause:** Wires and switches change the effective resistance and
capacitance seen by each RC node. `i_C = C dV/dt` links capacitance to slew;
the first-order crossing delay is `R C ln(2)` for a half-supply threshold.
Selected branches can have different parasitics, disturbing bit weights and
the 512 kHz trim. These are predictions until connected-layout PEX and
transient checks exist.

**Candidates taught by the engineer:** Common-centroid capacitor placement,
or a fan with the MSB centered at one square edge and successive bits
spreading from it. The engineer selected the edge-anchored fan in FP-003;
the detailed unit assignment remains open.

**Decision path:** Count actual MIM instances per bit and stage. Estimate
square or rectangular array dimensions for each separate stage bank. Keep
the larger base MIM distinguishable from trim units. Sketch both patterns;
ask the engineer to correct the orientation and grouping. Only then propose
cell locations and routing. Compare extracted branch R/C, trim-step
monotonicity, waveform slew, and post-layout frequency before preferring one.

**Current counts and sketches:** See `knowledge/lab-book.md`, FP-002. No
physical layout change has been authorized for this teaching step.

## FP-003 — Use an edge-anchored fan for the first RCO bank proposal

**Source:** Engineer selection, 2026-11-12. Place the broad MSB region at
the middle of one bank edge and fan lower bits inward. Keep the larger base
MIM outside the trim grid near the RC node. Prioritize controlled RC delay
and trim behavior over common-centroid matching for this first proposal.

**Decision path:** Start with one bank per stage: 9 × 9 unit sites for SKY
or 8 × 8 for GF as a count-only sketch. Orient and assign bit regions only
after the engineer specifies which edge faces the resistor, switch, and
RC node. Preserve room for legal spacing and routing; do not treat open
sites as approved dummy cells. Keep common centroid as a comparison if
extracted trim errors or phase imbalance motivate it.

**Physics and test:** `i_C = C dV/dt`; parasitic R/C can change selected
branch loading, edge slew, stage delay, and ring period. With average stage
delays, `T ≈ 2Σt_stage`. The fan is a layout hypothesis until connected
DRC/LVS, PEX, transient waveforms, and trim-code checks are available.

## FP-004 — Align each bit's bank-facing capacitor region

**Source:** Engineer clarification, 2026-11-12. The lower-bit capacitors
fan away, while each bit's connecting capacitor or entry region stays on
the same row as the MSB. Do not interpret the fan as moving the bit taps
progressively farther from the shared bank-side row.

**Netlist interpretation:** Each stage has `n<i> → MAIN<i> → bank<i> →
SW<i>_<bit> → cap<i>_<bit> → MIM network → ground`. A series chain has one
first MIM at the bit node; parallel branches can have several. The MSB
contains 32 SKY or 16 GF parallel MIMs, so the final top-plate bus and
exact tap assignment need a separate routing design.

**Physical test:** Compare bit-entry path resistance, stray capacitance,
Elmore delay contribution, RC-node slew, adjacent trim steps, and stage
phase spacing in extracted layouts. A common geometric row does not imply
equal parasitics without matched routing layers, path lengths, vias, and
coupling environments. Keep this as a reviewed sketch until the engineer
chooses the edge and detailed MSB connection.
