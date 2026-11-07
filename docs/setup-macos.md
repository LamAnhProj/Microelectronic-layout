# Lightweight macOS setup

Run `bash scripts/bootstrap-macos.sh` from the checkout. Install Homebrew first
from https://brew.sh if absent. The script detects Apple Silicon/Intel and RAM,
and uses native Homebrew packages. It does not change SIP, Gatekeeper or firewall
settings. Inspect it before running. It does not request credentials.

Official package references:
- https://formulae.brew.sh/cask/klayout
- https://formulae.brew.sh/formula/ngspice
- https://www.klayout.org/klayout-pypi/

Open KLayout from Applications. Its GUI Python runtime and the project venv are
distinct. Installing the Python package does not connect to the interactive GUI.
Do not mix architecture-specific libraries.

On macOS 26.5.1, Homebrew disabled the KLayout cask. The official
[KLayout download page](https://www.klayout.de/build.html) provides an arm64
Tahoe 0.30.12 standalone DMG. Verify its published checksum before installing;
the build tested here is recorded in `docs/validation.md`. The official app has
an ad hoc signature and macOS may require user approval for Finder launch.
The direct executable at `/Applications/klayout.app/Contents/MacOS/klayout`
was used for the bridge tests. Do not disable Gatekeeper system-wide.

`.python-version` pins Python 3.13 for the available KLayout arm64 wheel.
Unpinned `uv` selected Python 3.15 on this Mac and attempted a large source
build of the geometry package.

## Optional Linux worker

Install Docker Desktop only when needed, from
https://docs.docker.com/desktop/setup/install/mac-install/ . Check `docker info`.
No second standalone Linux VM is needed.

```sh
make worker-build
make qualify
```

Alternatively use `bash scripts/bootstrap-macos.sh --with-worker`, which installs
the official Homebrew `docker-desktop` cask. Complete first-run prompts locally,
then rerun `make worker-build` and `make qualify` if Docker was not ready yet.
On the validated Mac, the cask could not create `/usr/local/bin` without an
interactive `sudo` prompt. Docker's official signed and notarized app was
installed directly instead, with its CLI linked from `/opt/homebrew/bin`.

The worker contains ngspice, pinned-source Magic, Netgen LVS, Xschem, KLayout and
Xvfb, without a PDK. KLayout GUI APIs are tested in hidden-view mode; no remote
desktop is exposed. Xschem's interactive macOS
setup is deferred until we choose a PDK and GUI strategy; textual SPICE works now.
On arm64, Netgen is also built from a pinned upstream revision because the
Debian package lacked its Tcl library in the first Mac build.

The runtime has no network, a read-only root filesystem, dropped capabilities,
a process limit, one CPU, a 1-GiB RAM ceiling, and one writable results mount.
It receives no home directory, Docker socket or R2 credentials. Containers reduce
access but are not a complete security boundary for untrusted binaries. Builds
need network access to package registries.

Compose defaults to UID/GID 1000. Docker Desktop handles macOS bind mounts. On a
Linux host with different IDs use:

```sh
LAB_UID="$(id -u)" LAB_GID="$(id -g)" docker compose run --rm worker
```

For a Mac with 8 GiB RAM or less, favor native tools and remote Linux compute.
If using Docker, run one small job at a time and quit Docker afterward. The
container limit is separate from the Docker VM's RAM allocation. Configure that
in https://docs.docker.com/desktop/settings-and-maintenance/settings/ .

Testing in the ChatGPT cloud workspace does not install anything on your Mac.
Run the bootstrap locally and keep the `doctor` output before larger jobs.
For live KLayout control use `docs/bridge.md`. The socket and agent must run
on the same machine; a cloud agent cannot directly reach a Mac-local socket.

Python dependencies are locked in `uv.lock`. Homebrew and Debian versions resolve
at installation/build time. Record tool inventories and image IDs; pin a worker
image digest and PDK/deck revisions before design comparisons or fabrication.
