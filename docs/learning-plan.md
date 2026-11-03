# Building engineering judgment

Build an agent that predicts, retrieves evidence, runs controlled experiments and
learns from results. A corpus alone does not make it equivalent to a PhD engineer.
Measure transfer to unseen circuits.

## Curriculum

1. KCL/KVL, impedance, poles/zeros, noise and transients.
2. MOS regions, gm/Id, body effect, capacitances, model limits, mismatch and temperature.
3. Mirrors, differential pairs, gain stages, feedback, stability, biasing, references.
4. Layout matching, orientation, dummies, wells/taps, shielding, return paths,
   coupling, parasitics, reliability and actual process rules.
5. CMOS logic, timing, metastability, CDC, power, arithmetic and memory organization.
6. DRC/LVS/PEX, corners, statistical mismatch where supported, packaging and measurement.

Primary teaching references to consult, not bulk-copy:
- [MIT 6.012](https://ocw.mit.edu/courses/6-012-microelectronic-devices-and-circuits-fall-2009/).
- [Advanced Integrated Circuits](https://analogicus.com/aic2026/).
- Official process documentation and tool manuals in `config/sources.json`.

Review licenses for redistribution and training; open access is not unrestricted
reuse. Start with links and original notes. The included notes are project-authored
teaching aids, not an imported course or comprehensive validated knowledge base.

## Exercise ladder

RC filter (included) -> inverter -> current mirror -> differential pair -> OTA ->
compensated amplifier -> comparator -> small mixed-signal block.
For each: predict -> simulate -> explain discrepancies -> lay out -> verify ->
extract -> compare again. Record failed hypotheses too.

## Dataset admission and evaluation

Record URL, commit, license, provenance, model/PDK, topology family, units,
corners, testbench, expected observables and validation status. Schematic-only
data is not verified layout data. Never execute retrieved scripts automatically.

Split by topology/cell family and source design before sweeps or perturbations.
Hold out entire families to detect memorization. Compare with analytic baselines
and independent verification. Store inputs, predictions, tool calls, output hashes,
metrics, and accept/reject rationale. Do not reward LVS alone: check DRC, device
preservation and circuit performance.

Start with SQLite retrieval. Add embeddings only if evaluation justifies the
memory cost. Fine-tuning needs clean traces and a held-out benchmark first;
GPU workloads belong on remote compute.
