#!/usr/bin/env bash
set -euo pipefail
LAB_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
if [[ $# -lt 2 || $# -gt 3 ]]; then
  echo 'Usage: bash scripts/start-klayout-bridge.sh LAYOUT CELL [TECHNOLOGY_JSON]' >&2
  exit 2
fi
if command -v klayout >/dev/null; then
  LAB_KLAYOUT="$(command -v klayout)"
elif [[ -x /Applications/klayout.app/Contents/MacOS/klayout ]]; then
  LAB_KLAYOUT=/Applications/klayout.app/Contents/MacOS/klayout
else
  echo 'KLayout GUI is missing. Run the macOS bootstrap first.' >&2
  exit 1
fi
export LAB_BRIDGE_LAYOUT="$1" LAB_BRIDGE_CELL="$2"
export LAB_BRIDGE_TECH="${3:-$LAB_ROOT/config/technology-scratch.json}"
exec "$LAB_KLAYOUT" -e -rr "$LAB_ROOT/bridge/start_klayout_bridge.py"
