# PDK and circuit-source shortlist

The machine-readable registry in `config/sources.json` records observed upstream
commit IDs, repository license metadata and archive status. These are discovery
records, not tested toolchain locks. A pinned SKY130A primitive-library subset
is now installed locally under ignored `pdks/volare/`; no circuit corpus or
other full PDK is downloaded. See `docs/validation.md` for its limited check.

- SKY130: start with its documentation and the current open-pdks/ciel installation
  path, rather than copying the entire source tree onto the Mac.
- GF180MCU: the original Google repository is archived; evaluate the FOSSi
  Foundation repository and libraries used by current open-pdks.
- IHP SG13G2: a candidate for analog/mixed-signal/RF work with its own models,
  tools and process requirements. It is not a drop-in substitute for SKY130.

Primary installation references:
- https://www.opencircuitdesign.com/open_pdks/open_pdks.html
- https://github.com/fossi-foundation/open-pdks
- https://github.com/fossi-foundation/ciel
- https://ihp-open-pdk-docs.readthedocs.io/en/latest/install/installation.html

Choose the device/voltage needs, available fabrication route, supported tool
versions and verification coverage before committing to a process. Start with
one pinned installed subset on a compute worker, then materialize the active
layout/model subset on the Mac only as needed.

The worker's SKY130A inverter check uses Magic 8.3.686 and one exact Volare
revision. This does not qualify the worker for other PDKs or a fabrication
signoff flow. For example, the current GF180 open-pdks Magic technology file
declares `requires magic-8.3.411`:
https://github.com/fossi-foundation/open-pdks/blob/main/gf180mcu/magic/gf180mcu.tech .
The worker now builds Magic from a pinned source revision, replacing the old
distribution package. Still test the exact deck/tool combination. IHP documents
process-specific model compilation and recommends a recent
Xschem source release. Build/pin compatible tools together with the chosen PDK.

For initial circuit examples, evaluate AnalogGym and ALIGN-public's examples.
They serve different purposes; neither is assumed to be a verified layout
training corpus. Inspect each example's models, technology, license, testbench
and expected metrics before importing it. Keep raw data in R2 and provenance
manifests in Git. See `docs/learning-plan.md` for validation and held-out splits.
