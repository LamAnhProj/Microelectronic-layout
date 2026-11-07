# Scaffold validation

## Mac validation — 2026-11-07

Run on the user's macOS 26.5.1 arm64 laptop (8 GiB RAM), separately from the
earlier Linux x86_64 cloud tests below. Git history from the setup bundle was
restored and normal-pushed to `LamAnhProj/Microelectronic-layout` master.

- Native Git 2.56.0, gh 2.103.3, uv 0.13.7, ngspice 47, rclone 1.76.0,
  KLayout application and Python geometry core 0.30.12. Python is pinned to
  3.13 in `.python-version` so the arm64 KLayout wheel is used.
- `make test`: 11/11 passed, including the live macOS Cocoa KLayout bridge.
  `make index`, search, scratch GDS round trip, and the manifest RC run passed.
  The RC measurement was 159158 Hz against 159154.943 Hz analytic.
- Docker Desktop 4.98.0 on Apple Silicon: VM 2 CPUs, 3 GiB RAM, 1 GiB swap,
  40 GiB disk ceiling. The Compose worker has a separate 1 CPU, 1 GiB limit.
  `make qualify`: 6/6 passed in the arm64 worker. Qualification report:
  `runs/34691144-89f9-4282-a6da-5006743df264/qualification.json`.
  Worker image ID: `sha256:1ae56b5ec50120056697355ee83a9775f8c82ea36059bc25810d8c6880c9d109`.
- Debian's arm64 `netgen-lvs` package lacked `tclnetgen.so` here. The worker
  now builds upstream Netgen revision `93dcda14d36349d0b0ca63168d3cbbab20fe2ece`
  (version 1.5.327) and checks for that library during the build.
- Homebrew's KLayout cask was disabled after a macOS Gatekeeper failure. The
  official arm64 Tahoe 0.30.12 DMG was checked against its published MD5 and
  installed directly. Its executable and live bridge tests pass; the app has
  only an ad hoc signature, so normal Finder launch can require user approval
  in macOS Privacy & Security.

These are tool and synthetic-fixture checks. No foundry PDK, device models,
process decks, or extracted transistor-level circuit has been qualified.

## Earlier cloud validation — 2026-11-03

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
