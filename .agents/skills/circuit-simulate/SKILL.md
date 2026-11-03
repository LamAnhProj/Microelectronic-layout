---
name: circuit-simulate
description: Predict and simulate SPICE circuit behavior, inspect measured results and compare pre/post-layout experiments with controlled assumptions.
---

1. Identify topology, supply, units, load, input, models and expected behavior.
2. Retrieve notes: `uv run --frozen --extra layout chip-lab search 'YOUR TOPIC'`.
3. Write the analytic prediction and valid assumptions before simulation.
4. For baseline tool validation run `make smoke`, or `make worker-smoke` with Docker.
5. Inspect `runs/<uuid>/result.json` and the full simulator log. RC cutoff must
   be within 1% of 1/(2*pi*R*C); exit success alone is not acceptance.
6. For new blocks write a `design.json` manifest modeled on
   `examples/rc_lowpass/design.json`, listing input files and expected measurements
   with units/tolerances. Run `chip-lab run-circuit PATH/design.json` locally.
   In the worker, place files under `runs/projects/NAME/` and run
   `docker compose run --rm worker run-circuit /results/projects/NAME/design.json --output /results`.
   Review simulator source input first; materialize and record model dependencies.
   A successful tool exit without the declared measurements is a failure.
7. For PEX compare identical testbenches/model corners and explain differences.

Read `knowledge/circuit-reasoning.md`. Do not present generic models as foundry
devices, nominal results as yield, or simulations as silicon measurements.
