#!/usr/bin/env bash
set -euo pipefail
if [[ "$(uname -s)" != Darwin ]]; then
  echo 'This installer is for macOS. Use Docker or a Python environment on other systems.' >&2
  exit 1
fi
LAB_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$LAB_ROOT"
LAB_WITH_WORKER=false
case "${1:-}" in
  '') ;;
  --with-worker) LAB_WITH_WORKER=true ;;
  *) echo 'Usage: bash scripts/bootstrap-macos.sh [--with-worker]' >&2; exit 2 ;;
esac
echo "Detected architecture: $(uname -m)"
echo "Physical RAM bytes: $(sysctl -n hw.memsize)"
if ! command -v brew >/dev/null; then
  echo 'Install Homebrew from https://brew.sh, open a new Terminal, then rerun this script.' >&2
  exit 1
fi
# Default: native tools. Linux EDA tools can be installed with --with-worker.
brew install git gh uv ngspice rclone
if [[ ! -d /Applications/klayout.app ]] && ! brew list --cask klayout >/dev/null 2>&1; then
  brew install --cask klayout
fi
uv sync --frozen --extra layout
uv run --frozen --extra layout chip-lab doctor
uv run --frozen --extra layout chip-lab index
uv run --frozen --extra layout chip-lab simulate
uv run --frozen --extra layout chip-lab layout-smoke
uv run --frozen --extra layout python -m unittest discover -s tests -p test_bridge.py -v
if [[ "$LAB_WITH_WORKER" == true ]]; then
  if [[ ! -d /Applications/Docker.app ]]; then
    brew install --cask docker-desktop
  fi
  open -a Docker
  if ! docker info >/dev/null 2>&1; then
    echo 'Complete Docker Desktop first-run setup, then run: make worker-build && make qualify'
    exit 0
  fi
  make worker-build
  make qualify
fi
echo 'Native setup complete. Bridge instructions: docs/bridge.md. Full worker: --with-worker.'
