#!/usr/bin/env bash
set -euo pipefail
if [[ "$(uname -s)" != Darwin ]]; then
  echo 'This installer is for macOS. Use Docker or a Python environment on other systems.' >&2
  exit 1
fi
LAB_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$LAB_ROOT"
echo "Detected architecture: $(uname -m)"
echo "Physical RAM bytes: $(sysctl -n hw.memsize)"
if ! command -v brew >/dev/null; then
  echo 'Install Homebrew from https://brew.sh, open a new Terminal, then rerun this script.' >&2
  exit 1
fi
# Native tools only. Docker, full PDKs, datasets and local models are not installed here.
brew install git uv ngspice rclone
if [[ ! -d /Applications/klayout.app ]] && ! brew list --cask klayout >/dev/null 2>&1; then
  brew install --cask klayout
fi
uv sync --frozen --extra layout
uv run --frozen --extra layout chip-lab doctor
uv run --frozen --extra layout chip-lab index
uv run --frozen --extra layout chip-lab simulate
uv run --frozen --extra layout chip-lab layout-smoke
echo 'Native setup complete. Docker remains optional; see docs/setup-macos.md.'
