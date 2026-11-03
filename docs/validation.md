# Bootstrap validation

Tested on 2026-11-03 in the managed Linux x86_64 workspace, not on the Mac.

- Python package installed in an isolated environment with KLayout core 0.30.12.
- Unit checks cover measured RC acceptance/rejection, private/exclusive reports,
  and reference search with query punctuation.
- SQLite FTS5 indexed three original engineering notes and retrieved matching/
  parasitics references.
- KLayout wrote and reopened a scratch GDS: one rectangle on synthetic layer
  1/0, 1 nm database units, 2 square micrometers area. Read-only inventory checked.
- Docker worker built and ran ngspice under the Compose restrictions: no runtime
  network, read-only root, non-root user, dropped capabilities, 1 CPU, 1 GiB RAM.
- RC measurement: 159158 Hz; analytic 159154.943 Hz; approximately 0.00192% error,
  within the 1% acceptance threshold. Result JSON used mode 0600 and was visible
  through the host results mount.
- Shell syntax and Git whitespace checks passed.

The baseline Debian worker includes ngspice 39.3, Magic 8.3.105, Netgen LVS
1.5.133 and Xschem 2.8.1. These distribution packages establish a runnable
bootstrap; do not assume compatibility with a newer PDK/model/deck. Qualify or
replace them together with the selected PDK before process design work.

Not tested/configured: macOS execution (Intel or Apple Silicon), Homebrew GUI
installation, R2 credentials/transfers, remote compute, production layout edits,
interactive editor bridge, any PDK-specific DRC/LVS/PEX, or fabrication acceptance.
