# Debug with evidence

Check target/technology -> units/supply -> connectivity/device identity -> bias
-> testbench -> numerical settings -> metrics. Changing convergence settings
first can hide circuit errors.

Fix design, testbench, model revision and tool version when comparing an edit.
A different model corner is a different experiment. Bind results to input hashes.

Clean LVS can be misleading with the wrong top cell, black boxes or exclusions.
Check expected ports/device counts. Empty DRC output can mean execution failed
or layers were mapped incorrectly. Exercise the flow with known-good and broken
cells. Missing reports mean unknown, not clean.

Digital setup/hold and metastability need appropriate analysis; RTL simulation
alone is not CDC verification. Analog nominal success says nothing by itself
about corners, mismatch yield or extracted behavior.

Record hypothesis, assumptions, prediction, input hashes, PDK/deck versions,
testbench, command, tool version, measured results, failure category, decision and
next discriminating experiment. Separate synthetic, simulated, extracted and
silicon-measured evidence.
