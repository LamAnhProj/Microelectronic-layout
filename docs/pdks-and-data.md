# PDK and circuit-source shortlist

The machine-readable registry in `config/sources.json` records observed upstream
commit IDs, repository license metadata and archive status. These are discovery
records, not tested toolchain locks. Pinned SKY130A and GF180MCU primitive
subsets are installed locally under ignored `pdks/volare/`; no circuit corpus or
complete standard-cell/IO bundle was requested. See `docs/validation.md` for
the process-specific checks.

- SKY130: start with its documentation and the current open-pdks/ciel installation
  path, rather than copying the entire source tree onto the Mac.
- GF180MCU: the installed Volare/open-pdks primitive bundle exposes variants
  A/B/C/D at revision `c6d73a35f524070e85faff4a6a9eef49553ebc2b`.
  The circuit diagnostic selects D; its physical flow is still incomplete.
- IHP SG13G2: a candidate for analog/mixed-signal/RF work with its own models,
  tools and process requirements. It is not a drop-in substitute for SKY130.

Primary installation references:
- https://www.opencircuitdesign.com/open_pdks/open_pdks.html
- https://github.com/fossi-foundation/open-pdks
- https://github.com/fossi-foundation/ciel
- https://ihp-open-pdk-docs.readthedocs.io/en/latest/install/installation.html

Choose the device/voltage needs, available fabrication route, supported tool
versions and verification coverage before committing to a process. The current
Mac has both primitive sets for local experiments, with about 214 MiB for
SKY130A and 2 GiB for GF180MCU. Neither is a qualified foundry installation.

The worker's SKY130A inverter check uses Magic 8.3.686 and one exact Volare
revision. This does not qualify the worker for other PDKs or a fabrication
signoff flow. The GF180 open-pdks Magic technology file declares
`requires magic-8.3.411`:
https://github.com/fossi-foundation/open-pdks/blob/main/gf180mcu/magic/gf180mcu.tech .
The worker now builds Magic from a pinned source revision, replacing the old
distribution package. The installed GF180 D deck loads under Magic 8.3.686,
but its default transistor generators are not DRC-clean and the native KLayout
runset's logger needs a macOS adapter. IHP documents
process-specific model compilation and recommends a recent
Xschem source release. Build/pin compatible tools together with the chosen PDK.

For initial circuit examples, evaluate AnalogGym and ALIGN-public's examples.
They serve different purposes; neither is assumed to be a verified layout
training corpus. Inspect each example's models, technology, license, testbench
and expected metrics before importing it. Keep raw data in R2 and provenance
manifests in Git. See `docs/learning-plan.md` for validation and held-out splits.
