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
