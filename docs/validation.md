# Scaffold validation

Tested on 2026-11-03 in the managed Linux x86_64 workspace, not on the Mac.

Host Python environment: KLayout core 0.30.12. Eleven tests discovered; nine pass
there and two require the worker's native executables. Those GUI/simulation
cases are exercised separately inside the worker, rather than claimed as passed
from a skipped host test.

The worker's six qualification checks pass:
1. Actual ngspice RC simulation: cutoff 159158 Hz versus analytic 159154.943 Hz,
   approximately 0.00192% error within the 1% threshold.
2. Pinned-source Magic starts headlessly and accepts Tcl commands.
3. Xschem version probe succeeds; interactive schematic operation is not tested.
4. Netgen distinguishes a matching generic circuit and an intentional mismatch.
5. KLayout's synthetic width DRC reports zero violations for the good fixture
   and one for the intentionally narrow rectangle.
6. KLayout application/Qt bridge: inspect, unsaved edit, separate snapshot save,
   original-file preservation, active-cell refusal and clean socket shutdown.
   The application uses hidden views (-z), not database-only batch mode (-zz).

Additional checks: stale hierarchy/properties fingerprints, wrong targets,
nonfinite/off-grid geometry, missing edit/save flags, duplicate job IDs, external
file changes, local socket authentication, private/exclusive reports, reference
search punctuation, and manifest circuit acceptance/rejection.

The packaged worker uses KLayout 0.30.0, ngspice 44.2, Netgen LVS 1.5.133, Xschem
3.4.4, and Magic source revision d914f66693e6ce0bd30dc1f2b265c2bcd7b20762.
It runs under the Compose restrictions: no runtime network, read-only root,
non-root user, dropped capabilities, one CPU, 1 GiB RAM, and a results mount.

SQLite indexes three original teaching notes. The scratch GDS round trip checks
one rectangle on synthetic layer 1/0, 1 nm DBU and 2 square micrometers area.
Shell syntax and Git whitespace checks pass. Run `make test` and `make qualify`
to reproduce checks and obtain local UUID reports.

Not tested/configured: macOS/Apple Silicon execution, Homebrew GUI installation,
R2 credentials/transfers, remote compute provisioning, foundry PDK models/decks,
PCells, automatic routing, process-specific DRC/LVS/PEX or fabrication acceptance.
