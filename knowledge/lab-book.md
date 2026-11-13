# Chip Lab book

This is the running design and teaching record. The engineer supplies layout logic,
physical intuition, and corrections. The agent writes decision paths, predictions,
and checks. A taught rule is recorded as **engineer guidance** until the selected
PDK, layout, and measurements support its application to a particular design.
Keep earlier entries when a rule changes; append a correction and link the evidence.

## 2026-11-12 — Floorplanning method begins

**Circuit:** nine-bit trimmed, three-stage RCO targeting 512 kHz. The controls
are 1.8 V. SKY130A uses a 1.8 V core; GF180MCU D uses a 3.3 V core with level
shifting. Both are open PDK learning variants.

**Current physical evidence:** device placements exist for both PDKs. They are
unrouted; placement DRC does not establish connectivity, LVS, PEX, or
post-layout frequency. See `examples/rco/README.md` and the saved placement
reports under the Git-ignored `runs/rco/placement/` tree.

**Teaching agreement:** the engineer will provide floorplanning logic, physical
grounding, and corrections. The agent will translate that into concise decision
conditions and iteration steps, and will explain each application. The agent will
keep its proposals separate from engineer guidance and measured results.

**Skill access:** Codex uses the skill name and description to decide when to
load `.agents/skills/floorplan/SKILL.md`. The entry point holds the decision
path; focused references hold concepts as they are taught. The skill is also
linked at `~/.codex/skills/floorplan` on this Mac for discovery from other
workspaces in a fresh session. The engineer can invoke it as `$floorplan`.

**Next observation:** no instructor placement rule has been recorded yet. Begin
with the first placement choice and its physical reason.

## 2026-11-12 — FP-001: Shape and area before placement

**Engineer guidance:** Start a real die with its shape and area. Assess signal
flow and the large circuit components. In this free-rein RCO, aim for the best
post-layout performance against the specifications. Make the block easy to
place at top-chip level, ideally square or with orthogonal protrusions.

**Agent interpretation:** Treat the outline as an integration and routing
constraint, and post-layout circuit measurements as the performance test. A
square bounding box is a candidate shape, not proof that wire parasitics or
frequency are optimal. The engineer has not yet specified a die boundary,
area limit, neighboring blocks, pin edge, or ranking among power, area, trim
resolution, and frequency error. The existing RCO construction targets include
512 kHz within ±1% after trim at nominal conditions, 45–55% duty as an aim,
and a buffered output swing into the modeled 1 pF load; these remain to be
checked after routing and extraction.

**Current signal flow:** Three inverter → resistor → RC-input stages form a
closed ring. Each RC input has a base capacitor and a nine-bit selected bank;
one control word and a master switch control the three banks. Control
restoration or level shifting feeds the switches. Two output inverters buffer
the ring. Major physical groups are the three long resistors, three capacitor
banks, ring MOS devices and switches, control circuits, and output buffers.
The placements contain 130 MOS devices and three resistors each, plus 234 SKY
or 186 GF MIM capacitors. See `examples/rco/README.md` for the source topology.

**Measured placement extent:** The table uses each saved GDS report's drawn
geometry bounding box; it is not a reserved block outline or routed footprint.

| Open PDK | Saved placement run | GDS bbox (µm) | Width × height (µm) | Bbox area (mm²) | Aspect | Placement DRC |
| --- | --- | --- | --- | ---: | ---: | --- |
| SKY130A | `7043cefd-a48b-4520-a828-baa9b2fae902` | `(34.79, 24.79)–(1041.10, 1032.215)` | `1006.310 × 1007.425` | 1.0138 | 1.0011 | 0 Magic / 0 KLayout items |
| GF180MCU D | `f78e0a3b-c334-47cf-b6d6-b1144a8208c5` | `(34.70, 24.70)–(1042.40, 1032.30)` | `1007.700 × 1007.600` | 1.0154 | 1.0001 | 0 Magic / 0 KLayout items |

The corresponding GDS SHA256 values are
`8be4dffbd0c539618c9f0e2c7ac0bf36a178bf7f2f3e225a567991895b0913e1`
and
`252534423cdd6bf92f837cafeb6e3ccfd6b80f1870566f4ffc6d30d2c322e83a`.
Both reports use Volare PDK pin
`c6d73a35f524070e85faff4a6a9eef49553ebc2b` on the arm64 Mac.

**Assessment:** The current bounding boxes are square-like, but the generated
placement puts capacitor origins in a lower band and MOS origins in an upper
band. It was made to check PDK PCell population and placement DRC, without
connected routing. No top-level integration outline, routed area, LVS, PEX,
or post-layout frequency has been measured for this RCO. Its present shape
does not establish the engineer's performance goal.

**Next decision to learn:** How should the RCO's signal flow and major blocks
be arranged within that shape before routing? Record the engineer's reason,
then compare a candidate arrangement with this baseline.

## 2026-11-12 — FP-002: Capacitor banks first

**Engineer correction:** The current square-looking placement is poor because
the function of the circuit matters more than its bounding-box shape. The
nine-bit trim capacitor banks are critical. Their wiring resistance and
capacitance affect the RC-node edge slew and stage timing. Assemble the
capacitor banks first; consider either common-centroid placement or a fan
arrangement with the MSB at the middle of one square edge and successively
less significant bits spreading in fan-like regions.

**Terminology:** Edge slew is `dV/dt`; timing skew is a difference between
arrival times. Both can change with parasitic RC, but the requested physical
concern here is the RC-node waveform and the trim steps. For a first-order
single-node estimate, `i_C = C dV/dt` and `t_50 ≈ R C ln(2)`. Distributed
wire resistance and capacitance require the actual routed network; this
estimate does not determine the preferred geometry.

**Verified device inventory from the current schematic generator:** Each of
the three stages has one larger base MIM and the following trim-unit MIM
counts. This is a count of PDK capacitor instances, not equal physical area.

| PDK | Bit 0 → bit 8 unit counts | Trim units / stage | Base MIM / stage | All MIMs / stage | Three-stage total |
| --- | --- | ---: | ---: | ---: | ---: |
| SKY130A binary | 8, 4, 2, 1, 2, 4, 8, 16, 32 | 77 | 1 | 78 | 234 |
| GF180MCU D balanced | 16, 8, 4, 2, 1, 2, 4, 8, 16 | 61 | 1 | 62 | 186 |

**Agent grid proposal for one trim bank, keeping the base MIM separate:**

| PDK | Near-square grid | Open sites | Rectangular option | Open sites |
| --- | ---: | ---: | ---: | ---: |
| SKY130A | 9 rows × 9 columns = 81 | 4 | 8 × 10 = 80 | 3 |
| GF180MCU D | 8 rows × 8 columns = 64 | 3 | 7 × 9 = 63 | 2 |

Counting all three stages in one array would give 231 SKY or 183 GF trim
units: a 15 × 16 grid has nine open sites for SKY, while a 14 × 14 grid has
13 for GF. These are arithmetic packings only. The three banks connect to
different RC nodes, so one shared array is not a placement decision yet.

The open sites are *planning capacity*, not approved dummy cells or empty
fabrication sites. If a base MIM is counted as one site, 9 × 9 leaves three
sites on SKY and 8 × 8 leaves two on GF; this is geometrically misleading
because the base MIM is much larger than a trim unit. SKY trim units use a
4.5 µm plate width. GF balanced trim units vary from 5 to 7 µm; both base
plates are about 15.6–15.7 µm. Legal cell pitch, routing channels, edge
dummies, and the true bank outline remain to be determined from the PDKs.

**Rough pattern only; not unit-cell placement:**

```text
COMMON CENTROID                 EDGE-ANCHORED FAN (assumed inward spread)
┌─────────────────────┐         ┌─────────────────────────┐
│ mirrored bit groups │         │ outer, lower bits       │
│    ↘    ↓    ↙      │         │   C6   C5   C4   C6    │
│       center        │         │    C7         C7       │
│    ↗    ↑    ↖      │         │      broad C8 zone      │
│ mirrored bit groups │         │      broad C8 zone      │
└─────────────────────┘         └────center of edge───────┘
```

In either sketch, `C8` denotes a **region containing many unit capacitors**:
32 in SKY and 16 in GF, not one device. The exact bit tiling and routing are
not drawn. The fan orientation, switch and RC-node locations, and whether the
base MIM sits inside or beside the trim array need the engineer's decision.
No GDS, DRC, LVS, or PEX was generated for these proposals.

## Entry format for each taught concept

Record the engineer's statement in ordinary language first. Then add:

1. **Scope:** circuit block, process, operating condition, and revision.
2. **Physical model:** current path, electric field, parasitic, matching, or
   thermal mechanism; include units and a formula when useful.
3. **Decision path:** the condition, action, and exception in compact form.
4. **Prediction:** what waveform, frequency, power, area, or verification result
   should change, and in which direction.
5. **Evidence:** exact layout/netlist/PDK hashes, tool and deck versions, run ID,
   measured result, and discrepancy. Use `unknown` when a check has not run.
6. **Revision:** correction or next experiment, retaining the earlier reasoning.
