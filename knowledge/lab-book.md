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

**Initial rough pattern, corrected by FP-004; not unit-cell placement:**

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

## 2026-11-12 — FP-003: Select the edge-anchored fan

**Engineer selection:** Use the edge-anchored fan. Put the MSB region at the
center of one bank edge and spread the successively lower bits inward. Keep
the larger base capacitor outside the trim-unit grid near the RC node.
Matching is a lower priority here than controlling the RC delay and the
timing shifts caused by the trim-bank parasitics. This supersedes the
common-centroid option for the first physical proposal; common centroid
remains a comparison option if measured behavior later warrants it.

**Agent interpretation:** The target is a predictable effective capacitance
and transition time for each selected trim code. Wire and switch resistance
and parasitic capacitance can change the RC-node slew `dV/dt`. If the three
stages acquire different delays, their edges shift relative to one another;
the ring period also changes. Using average stage delays, a first-order model
is `T ≈ 2(t0 + t1 + t2)` and `f ≈ 1/T`. This explains the engineer's skew
concern without claiming that the fan has already improved frequency or
phase. A static trim word does not itself create a separate clock phase.

**Current sketch decision:** Keep one 9 × 9 SKY trim grid or one 8 × 8 GF trim
grid per stage as the count-based starting point. The MSB is a broad region
of 32 SKY or 16 GF unit MIMs, not a single tile. Lower-bit regions fan inward.
The exact unit allocation, edge orientation relative to the resistor and
master switch, and route topology are still open. Matching is lower priority,
not an unchecked property; inspect trim monotonicity and stage-to-stage
delay after extraction.

**Evidence and state:** This is an engineer-selected plan. No new GDS or
post-layout R/C, DRC, LVS, or transient run has been made for the fan.

## 2026-11-12 — FP-004: Common connection row within the fan

**Engineer clarification:** As lower bits fan out, the capacitor that
connects each bit branch is on the same row as the MSB. The fan describes
where the rest of each bit's capacitance spreads; it does not move the
electrical entry points of lower bits away from the MSB connection row.

**Netlist mapping:** For each stage, `n<i>` reaches `bank<i>` through the
master transmission gate. Each bit switch connects `bank<i>` to
`cap<i>_<bit>`, the top node of that bit's MIM network. In a series chain,
the first MIM touches `cap<i>_<bit>`; in a parallel bit, several MIMs touch
that node. Thus the proposed common row holds the **bank-facing entry/tap
region** of each bit, with its remaining unit cells fanning into the array.
The MSB is many parallel units (32 SKY, 16 GF), so a literal single 9-site
or 8-site row cannot hold every MSB bank-facing plate. A local top-plate
spine along that row is an agent interpretation to examine, not yet an
engineer-approved route.

```text
                         interior of one stage bank
             lower-bit series/parallel units fan away
                 ↖       ↑       ↗
       ┌────────────────────────────────────────┐
       │ bit entry/tap regions  | broad MSB area│
       ├────────────────────────────────────────┤ ← common connection row
       │  SW0  SW1  ...  SW7  | SW8 / MSB edge │
       └────────────────────────────────────────┘
                shared bank-side routing corridor
```

**Why this may help:** The first part of each selected branch is close to a
defined row, making switch-to-cap routing more local and comparable. A
distributed RC network has a first-order Elmore delay
`t ≈ Σ R_segment × C_downstream`; resistance before a large downstream
capacitance is especially consequential. A fixed stray capacitance is also
a larger fraction of a small trim weight than of the MSB. For example,
1 fF would be 20% of an ideal 5 fF LSB if it appeared directly in parallel
at that branch node; this is an illustration, not a measured parasitic.
The real switch, series-MIM, and coupling network must be extracted.

**RCO consequence:** Added or unequal branch parasitics alter the effective
selected capacitance and RC-node slew. That changes each inverter's input
crossing time, stage-to-stage phase spacing, and potentially the ring period
and duty cycle. The shared row is a routing hypothesis to test, not a
guarantee of equal path resistance or capacitance. Layer, path length, vias,
neighbors, and ground return still matter.

**Open geometry:** Confirm whether the intended row is the bank-facing edge
next to the bit switches and how the MSB's many parallel units join it.
No layout, DRC, LVS, PEX, or new simulation was executed for FP-004.

## 2026-11-12 — FP-005: Mirrored entry row and dummy perimeter

**Engineer guidance:** The common connection row is the edge facing the bit
switches and shared bank route. Compare an edge-anchored fan against a
traditional common centroid in a separate cap-bank-and-switch testbench. Every
empty array site is a dummy tied to ground. Surround each bank with a dummy
ring. Both the rectangle and every bit's active cells should mirror left to
right. Build and test hierarchically.

**Geometry constraint and agent resolution:** Eight bit populations are even
and one is odd: bit 3 for SKY130A, bit 4 for GF180MCU D. A mirrored entry
row with one pair per even bit and one singleton needs `8×2 + 1 = 17`
columns. A 17×5 core gives one center row for the common-centroid option.
Both variants use this same core and a one-site dummy perimeter, producing
a 19×7 site rectangle. This is wider than the earlier count-only 9×9 or 8×8
sketches; the earlier sketches cannot meet the new per-bit mirrored entry-row
condition. The singleton occupies the center site, so the MSB's two entry
cells straddle it at columns 7 and 9. The MSB region is centered as a pair,
not one cell on the axis. Review this deliberate tradeoff in the [logical
maps](../examples/rco/bank-floorplans.svg).

**Population per stage:** SKY has 77 active trim MIMs, 8 internal dummy sites,
and 48 perimeter dummy sites. GF has 61 active, 24 internal dummies, and 48
perimeter dummies. The base MIM remains outside the grid. Dummies are actual
MIM PCells in the placement, but neither plate has been physically routed to
ground. The ground connection and its LVS evidence remain open.

**Standalone electrical baseline:** `examples/rco/bank_block.py` defines
`RCO_BANK` with one base MIM, a master transmission gate, nine bit transmission
gates, and PDK MIM networks. Its AC and transient bench uses ideal static
control levels. On native arm64 Mac ngspice, code 0 → 1 changed the SKY
effective capacitance from 544.081 to 552.932 fF and half-supply step delay
from 174.635 to 177.221 ns. GF changed 571.221 → 580.354 fF and
182.385 → 184.918 ns. Runs are under `runs/rco/bank_bench/`. These are
schematic-level results: fan and centroid have the same ideal netlist, so
their electrical results cannot differ until routed extraction exists.

## 2026-11-12 — FP-006: Non-minimum M4 corridor between MIM units

**Engineer request:** Check the design-rule manual for a wire between MIM
capacitors with more than minimum spacing, aiming to reduce parasitic
capacitance. This is a placement and routing hypothesis, not a measured
low-capacitance result.

**Rule evidence:** GF180MCU option B `MIMTM.1` requires 1.2 µm between a
MIM bottom plate and adjacent bottom-plate or unrelated routing metal.
Its ordinary M4 width/spacing minima are 0.28 µm. In the installed SKY130A
KLayout deck, `cap2m.2b_a` checks 1.2 µm between M4 bottom plates, and
`cap2m.11` checks 0.5 µm from the MIM marker to unrelated M4. The SKY130
M4 width minimum is 0.30 µm. Check the complete PCell shapes and deck
because these rules do not by themselves certify a wire with vias.
Sources: [GF MIM option B](https://gf180mcu-pdk.readthedocs.io/en/latest/physical_verification/design_manual/drm_10_4_2.html),
[GF Metaln rules](https://gf180mcu-pdk.readthedocs.io/en/latest/physical_verification/design_manual/drm_07_14.html),
[SKY130 periphery rules](https://skywater-pdk.readthedocs.io/en/main/rules/periphery.html),
and the pinned `pdks/volare/sky130A/libs.tech/klayout/drc/sky130A_mr.drc`.

**Agent corridor proposal:** Reserve a 0.5 µm wide M4 signal wire with
2.0 µm from each adjacent M4 plate edge: `2.0 + 0.5 + 2.0 = 4.5 µm`
plate-edge gap. This exceeds both PDKs' cited minima. From saved PCell GDS,
the widest SKY trim-unit M4 bbox is 7.99 µm across; the widest GF M4 bbox
is 9.40 µm. At a 14.0 µm site pitch, the calculated horizontal plate gaps
are at least 6.01 µm SKY and 4.60 µm GF. The vertical gaps are larger for
the measured units. This clearance is
for **one straight wire between units**. Via landing, turns, PCell pins,
other metal shapes, and dummy ground ties require a routed DRC check.

**Physics and sweep:** A larger side gap tends to reduce lateral coupling
approximately as `C_c ∝ εL/d` in a simple sidewall model. Increasing pitch
also lengthens wires, increasing `R_wire ∝ L/(w t)` and their ground/fringe
capacitance; a grounded shield can lower cross-coupling while increasing
signal-to-ground load. Therefore the widest possible spacing is not
automatically the fastest oscillator. Sweep plate gaps around 4.5, 6.5,
and 8.5 µm after routing; compare extracted per-bit R/C, transient delay,
trim monotonicity, 512 kHz trim error, and stage phase spacing.

**Correction during review:** An initial 12.5 µm pitch calculation mistook
GF GDS layer 41/0 (Via4) for Metal4. The actual Metal4 is 46/0; its wider
plate prompted the 14.0 µm pitch. The earlier 12.5 µm placement DRC was
clear, but it did not meet this *non-minimum* corridor target. The probe
must be checked on the real Metal4 layer after the correction.

**Native Mac check after correction:** All four 14.0 µm pitch placements
(SKY/GF × fan/centroid) have zero Magic errors and zero KLayout DRC items.
With a separate floating 0.5×3.0 µm M4 probe between active bit-7 and bit-8
entry PCells, GDS readback measures 2.755 µm side clearance in SKY and
2.05 µm in GF. Both probe layouts also have zero Magic errors and zero
KLayout DRC items. The probe was revised after a corner-origin placement
error caused its first version to overlap a plate; the validator now
explicitly rejects overlap and checks the measured GDS clearance. Final
verified probe runs are `d642239b-e81f-4eae-ba07-62da78c5936a` (SKY)
and `3a11063a-7881-4f21-8186-156d18967ed2` (GF), under
`runs/rco/bank_placement/`. The test wire is floating and only 3 µm long.
Route the actual bank signals, ground the dummies, run connected DRC/LVS
and PEX, then compare the variants electrically.

## 2026-11-12 — FP-007: Close the fan's central dummy channel

**Engineer correction:** The fan must not have a line of dummies through its
middle. Active capacitor units should be adjacent in a compact bank. Change
rows and columns as needed. The outer dummy ring and per-bit left/right
mirroring taught in FP-005 still apply.

**Why the first map had a channel:** Eight bit populations are even, and the
single odd-population bit occupies the entry-row axis. On a uniform 17-site
row, left/right mirroring forces every upper-row active unit to have a partner
on the other side of column 8; no unit can occupy that axis without breaking
the per-bit count or symmetry. Filling the axis with dummy PCells made a
continuous grounded-dummy channel, contrary to the new guidance.

**Agent geometry change:** Keep 17 sites on the switch-facing entry row.
Remove the central *site* from every upper fan row and shift the left and
right eight-site halves inward by half a 14.0 µm pitch. Their innermost
unit origins are now one pitch apart, so active cells are adjacent across
the former center. This is a compact, symmetric, staggered array with an
orthogonal step at the entry edge. SKY needs five active rows (17 + 4×16
capacity); GF needs four (17 + 3×16). In both, the only unfilled core sites
are two mirrored pairs at the far-row **outer** ends. All such sites and
the perimeter receive dummy MIM PCells. MIM plate polygons do not literally
touch: the PDK requires separation, and the 14.0 µm pitch preserves the
non-minimum corridor measured in FP-006.

**Comparison caveat:** The common-centroid option stays on its regular 17×5
grid. GF fan and centroid therefore differ in footprint as well as unit
ordering. Later PEX comparisons must report area and actual path lengths
with waveform and trim data; they cannot attribute every difference to the
placement pattern alone.

**Native Mac checks:** `examples/rco/bank_floorplan.py` rejects a fan map
with any unexpected interior hole. The [updated bank maps](../examples/rco/bank-floorplans.svg)
show adjacent upper-row active sites. SKY fan has 149 GDS PCell instances,
including 51 dummies; GF has 131, including 49 dummies. Both updated
placements passed Magic and KLayout with zero DRC findings. Both local M4
probes also passed with zero findings and retained the measured 2.755 µm
SKY and 2.05 µm GF plate clearance. The final fan placement run IDs are
`b56397a5-c7f0-4082-b813-0c82aeacaf90` (SKY) and
`7e6ebc6b-33ac-420e-8558-b3fa8977b752` (GF), under
`runs/rco/bank_placement/`. Ground ties, electrical LVS, and bank PEX
remain open.

## 2026-11-12 — FP-008: Uniform MIM grid for both bank patterns

**Engineer correction:** Active capacitor bits should occupy adjacent sites
in the common-centroid layout too. Do not stagger MIM capacitor rows.
This supersedes the staggered fan geometry in FP-007.

**Correction to the earlier reasoning:** FP-007 claimed the center column
could not hold active units above the singleton while preserving per-bit
left/right symmetry. That overlooked the MSB's **even** population. Placing
four MSB units on the center axis uses an even number of self-mirrored
positions, leaving its remaining units in mirrored pairs. The singleton
stays on the full row. This removes the dummy channel without shifting any
cell off the shared column lattice.

**Uniform-grid construction:** Both variants now use five rows by 17 columns
at 14.0 µm M4 bottom-plate center pitch. The fan's row 0 is fully active and faces the bit
switches. The common centroid's row 2 is fully active. The other four rows
have a centered contiguous active span: columns 1–15 for SKY (15 active per
row) and columns 3–13 for GF (11 active per row). In each of those rows,
column 8 holds one MSB unit. The counts are exact:
`17 + 4×15 = 77` SKY trim MIMs and `17 + 4×11 = 61` GF trim MIMs.
All remaining core sites are outer-edge dummies; a one-site dummy ring
surrounds the rectangle. Every active row has no gap between bit sites.
Each unit PCell origin is offset by half its measured M4 plate dimensions,
so the different GF unit widths still put their M4 plate centers on the
same x/y lattice. The actual plates retain their PDK-required separation
and do not literally touch.

**Common-centroid check:** Each bit remains mirrored left/right. The four
off-center MSB axis cells are at rows 0, 1, 3, and 4, balanced about row 2.
The remaining noncentral units are placed in left/right and top/bottom
quartets; two-unit groups sit as symmetric pairs on row 2. The generator
asserts each bit's mean row is 2 and mean column is 8. The GDS verifier
checks every unit M4 plate center against the same lattice. This establishes
a common M4 bottom-plate center for each bit group; electrical matching and
parasitic balance still require extraction.

**Native Mac evidence:** [Revised maps](../examples/rco/bank-floorplans.svg)
show both patterns with no interior dummy line or staggered row. All four
one-stage placements contain 154 PDK PCell instances. Native GDS readback
measured zero offset from the 14.0 µm lattice for every trim/dummy M4
bottom-plate center; Magic and KLayout each reported zero placement DRC
findings. The final run IDs under `runs/rco/bank_placement/` are
`be21f475-a91d-4400-bbca-7bfed6f3c28d` (SKY fan),
`483adde3-3e9c-436c-88dc-d57c6fdf024a` (SKY centroid),
`285ac6d4-42d8-43c7-b25c-6603f71c793c` (GF fan), and
`5ed0d1f0-bf80-4a60-a59c-7859f0b6529f` (GF centroid). The isolated
M4 fan probes again passed both DRC engines, with 2.755 µm SKY and
2.05 µm GF side clearance. These are placement and local-corridor checks.
Dummy plates still require ground routes; connected DRC, LVS, PEX, and the
bank delay comparison remain open.

## 2026-11-12 — FP-009: Keep every bit in one connected MIM cluster

**Engineer correction:** Unit capacitors of bit 8 must all touch as one
group; likewise bit 7 and every smaller bit. Move bit 8 to the fan's outer
edge so the other groups can pack together. Minimize avoidable routing gaps.
This tightens the earlier requirement that *all* active sites be contiguous:
each **individual bit** must now be edge-connected. Physical M4 plates
retain their PDK spacing; “touch” here means adjacent capacitor sites.

**Measured problem in FP-008:** In the previous fan, SKY bit groups 0, 1,
5, 6, and 7 split into four to eight disconnected site islands. The GF
fan likewise split most bits. In the exact centroid, the MSB alone split
into six site islands. A no-hole active rectangle therefore did not satisfy
the new routing constraint.

**Conflict with exact common centroid:** A one-unit bit's geometric
centroid lies at its grid-site center. The midpoint of two equal units
that share an edge lies halfway between two site centers. On an unstaggered
grid those centroids cannot coincide. SKY has a one-unit bit 3 and two-unit
bits 2 and 4; GF has a one-unit bit 4 and two-unit bits 3 and 5. Thus
"every bit edge-connected" and an **exact** common centroid of all nine
bit groups cannot both hold with the current unit counts. The old exact
interdigitated pattern remains in `bank-centroid-reference.svg` for
comparison; it is not relabeled as a touching-group layout.

**Agent fan proposal:** Use a four-row rectangular core. Allocate each
bit a vertical stripe of `ceil(unit_count / 4)` columns, with a serpentine
order through each full stripe. SKY needs 21 columns (`4×21 = 84` sites)
for 77 active units; GF needs 17 (`4×17 = 68`) for 61. The seven unused
sites in either core lie at the **outer left edge** above the partial
one- and two-unit stripes, never between active groups. Bit 8 occupies
the entire outer right block, with bit 7 and bit 6 alongside it. Every
bit has its first schematic unit on the bottom, switch-facing row.
The full dummy ring remains. The grid, same-bit connectivity, row
continuity, and entry condition are checked in `bank_floorplan.py`.

**Connected center-biased comparison:** The second main map uses the same
core and unit counts, but moves bit 8 near the center while keeping each
bit in one connected stripe. Its two-unit groups occupy rows 1–2, so
their midpoint is near the bank's vertical center; its singleton occupies
row 1. This is **not an exact common centroid** and is labeled as a
clustered reference. It tests whether centering the large MSB block
changes the extracted bank parasitics while preserving the new grouping
rule. The exact centroid remains a third, separate teaching reference.
On the 14.0 µm site grid, the MSB's horizontal site-center average moves
from 91 µm to the right of the core center in the fan to 7 µm from center
in the clustered reference (left for SKY, right for GF). This is placement
geometry, not a measured capacitance or delay improvement.

**Native Mac placement evidence:** The new SKY fan and clustered placement
each contain 159 PDK instances (77 trim MIMs, one base MIM, 20 switch MOS,
61 dummy MIMs). The GF equivalents each contain 135 (61 trim MIMs, one
base, 20 MOS, 53 dummies). All four passed Magic and KLayout placement DRC
with zero findings and zero measured offset from the 14.0 µm M4 plate-center
grid. Fan bit-7/8 local M4 probes retained 2.755 µm SKY and 2.05 µm GF
side clearance and passed both DRC engines. Saved runs are under
`runs/rco/bank_placement/`: SKY fan `9479ac4e-848c-45df-87d1-bc0e3638624e`,
SKY clustered `98ca53c8-2b7f-46a1-b62a-11e67f38172f`, GF fan
`6d934442-bb96-433b-9759-3fadf49b137b`, and GF clustered
`be3a453b-70aa-408b-867a-3957494a0c35`. The separate exact-centroid
references also pass placement DRC (SKY `dd6c41b5-5a09-4417-9252-6f55145dd59f`,
GF `dba88cfc-02c1-49df-b3de-c73a35892590`). These are **unrouted** layouts: dummy ground
ties, net continuity, LVS, extracted R/C, and delay/frequency comparisons
remain open. Use the [main comparison](../examples/rco/bank-floorplans.svg)
and [exact centroid reference](../examples/rco/bank-centroid-reference.svg)
to review the tradeoff.

## FP-010 · Restore the floorplan decision history

The current grouped drawing had replaced the earlier comparison SVG, making the
original mirrored fan, compact fan, and uniform-grid proposals hard to inspect.
The engineer requested that every version remain visible for comparison. The
four committed SVGs are now immutable, named snapshots under
[`examples/rco/floorplan-history/`](../examples/rco/floorplan-history/), with
the separate exact-centroid reference as a fifth entry. The [Chip Lab comparison
page](http://127.0.0.1:8765/floorplans/) displays any two revisions side by
side or stacked, with zoom and full-size links. The current grouped plan remains
the default on the right; the earliest mirrored plan is the default on the left.

**Decision history:** The first plan used a center dummy channel. The compact
revision removed it but staggered MIM rows. The next aligned all MIM centers
on a uniform grid, while several same-bit groups stayed separated. The latest
plan moves bit 8 to the outer fan edge and keeps each bit's units adjacent.
Its centered comparison is grouped, not an exact common centroid. The exact
centroid is retained separately because exact centroid and every-bit adjacency
conflict for the one-unit and two-unit weights on this grid.

**Scope of evidence:** These are one-stage logical placement maps for SKY130A
and GF180MCU D. Prior native Mac placement DRC results are recorded in the
corresponding entries above. The images are not routed netlists. Dummy ties,
LVS, PEX, and post-layout delay or frequency comparisons remain unknown.

## FP-011 · Interactive placement exercise and remaining-device count

The engineer requested movable versions of all saved floorplans and a visual
countdown of devices still to place. The [comparison page](http://127.0.0.1:8765/floorplans/)
now reads each saved SVG's actual site coordinates into an interactive one-stage
bank editor. Choose any historical revision and either PDK/proposal, then drag
or click MIM units to move them. Starting from an empty practice board makes
the remaining count descend from 77 SKY130A or 61 GF180MCU D trim units to
zero. The per-bit counter keeps the exact population of each trim bit visible.
The dummy perimeter stays fixed. Each panel has a separate browser-local draft,
undo and reset; a JSON download records a draft for later review.

**Teaching interpretation:** Each numbered tile represents one MIM unit, not
an entire binary-weighted bank or a routed device. Moving a unit changes a
logical placement proposal and may alter future route length and coupling.
The live counter measures inventory only. No wire resistance, capacitance,
phase shift, or frequency can be inferred from dragging a tile. A candidate
must later be translated into process-specific GDS, connected to switches,
have dummies actually tied to ground, and pass DRC, LVS, PEX, and transient
trim checks before comparing performance.

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
