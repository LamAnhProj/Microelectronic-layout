# Matching, routing, and parasitics

Original teaching note, not a PDK rule deck. Check the chosen process documents.

Matching depends on orientation, fingers, surroundings, wells/taps, stress,
routing and temperature. Common-centroid patterns can reduce some gradient
effects; they do not cancel arbitrary gradients, random mismatch or unequal
surroundings. Choose interdigitation/dummies for the physical error mechanism.

Do not assume mirroring/rotation preserves equivalence or rule legality. Check
allowed orientations, diffusion sharing, contacts and fingers against the PDK
and reference netlist.

For differential pairs and mirrors, compare complete electrical paths: contacts,
vias, metal width/length, coupling and terminal access. Equal geometric lengths
do not guarantee equal R/C. Shielding changes coupling but adds capacitance;
check bandwidth and reference impedance before choosing it.

Separate high-impedance nodes from aggressors. Inspect return paths and substrate
coupling. Wells/taps/guard structures are process-specific; preserve body nets.
Connectivity needs extraction, not labels alone.

DRC checks a particular deck's geometry rules. LVS compares extraction against
a schematic under matching settings. Neither establishes performance. Compare
PEX simulation with the same pre-layout testbench. Record extractor limitations.
EM/IR requires actual current, geometry, temperature and process limits; wider
wires or a basic DRC pass are not sufficient evidence.
