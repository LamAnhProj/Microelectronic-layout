#!/usr/bin/env bash
set -euo pipefail
LAB_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$LAB_ROOT"
if [[ $# -lt 2 || $# -gt 3 ]]; then
  echo 'Usage: bash scripts/archive-r2.sh runs|artifacts|data|pdks REMOTE:BUCKET [--upload]' >&2
  exit 2
fi
case "$1" in runs|artifacts|data|pdks) ;; *) echo 'Choose one approved artifact directory.' >&2; exit 2 ;; esac
case "$2" in *:*) ;; *) echo 'Destination must be REMOTE:BUCKET.' >&2; exit 2 ;; esac
if [[ "${3:-}" != '' && "${3:-}" != '--upload' ]]; then echo 'Unknown option.' >&2; exit 2; fi
[[ -d "$1" ]] || { echo "Directory does not exist: $1" >&2; exit 2; }
LAB_RCLONE_FLAGS=(--dry-run)
if [[ "${3:-}" == '--upload' ]]; then LAB_RCLONE_FLAGS=(); fi
# copy preserves local and remote files; do not use destructive sync.
rclone copy "$1" "${2%/}/$1" "${LAB_RCLONE_FLAGS[@]}" \
  --transfers 1 --checkers 2 --exclude '.env*' --exclude '*.key' --exclude '*.pem' \
  --exclude '*credentials*' --exclude '*.local.*' --exclude '*.conf' --exclude '*.sqlite*' \
  --exclude '.git/**' --exclude '.venv/**'
