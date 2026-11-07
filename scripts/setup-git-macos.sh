#!/usr/bin/env bash
# Restore the complete lab history, configure GitHub authentication, and publish.
set -euo pipefail

if [[ "$(uname -s)" != Darwin ]]; then
  echo 'Run this script in Terminal on your Mac; this machine is not macOS.' >&2
  exit 1
fi

LAB_ROOT="$(cd "$(dirname "$0")/.." && pwd -P)"
LAB_DEST="${1:-$HOME/Developer/Microelectronic-layout}"
LAB_BUNDLE="${2:-$LAB_ROOT/../Microelectronic-layout.bundle}"
LAB_ORIGIN=https://github.com/LamAnhProj/Microelectronic-layout.git
LAB_NEW_CLONE=false

if [[ $# -gt 2 ]]; then
  echo 'Usage: bash scripts/setup-git-macos.sh [CHECKOUT_DIRECTORY] [GIT_BUNDLE]' >&2
  exit 2
fi
if ! command -v brew >/dev/null; then
  echo 'Install Homebrew from https://brew.sh, open a new Terminal, and rerun.' >&2
  exit 1
fi
brew install git gh

LAB_EXISTING_ROOT="$(git -C "$LAB_ROOT" rev-parse --show-toplevel 2>/dev/null || true)"
if [[ "$LAB_EXISTING_ROOT" == "$LAB_ROOT" ]]; then
  LAB_REPO="$LAB_ROOT"
elif [[ -e "$LAB_DEST/.git" ]]; then
  LAB_REPO="$(cd "$LAB_DEST" && pwd -P)"
elif [[ -e "$LAB_DEST" ]]; then
  echo "Preserving existing directory without a Git checkout: $LAB_DEST" >&2
  echo 'Choose a different destination or have the agent inspect that directory.' >&2
  exit 1
else
  if [[ ! -f "$LAB_BUNDLE" ]]; then
    echo "Full-history Git bundle not found: $LAB_BUNDLE" >&2
    echo 'Use the complete Mac setup kit, or supply the bundle as the second argument.' >&2
    exit 1
  fi
  if [[ -z "$(git bundle list-heads "$LAB_BUNDLE" refs/heads/master)" ]]; then
    echo 'The bundle does not contain the expected master branch.' >&2
    exit 1
  fi
  mkdir -p "$(dirname "$LAB_DEST")"
  git clone --branch master "$LAB_BUNDLE" "$LAB_DEST"
  git -C "$LAB_DEST" bundle verify "$LAB_BUNDLE"
  LAB_REPO="$(cd "$LAB_DEST" && pwd -P)"
  LAB_NEW_CLONE=true
fi

if [[ -n "$(git -C "$LAB_REPO" status --porcelain)" ]]; then
  echo "Existing modifications preserved in $LAB_REPO. Review them before publication." >&2
  exit 1
fi
if [[ "$(git -C "$LAB_REPO" branch --show-current)" != master ]]; then
  echo 'The checkout is not on master. Have the agent inspect branches before publishing.' >&2
  exit 1
fi

if [[ "$LAB_NEW_CLONE" == true ]]; then
  git -C "$LAB_REPO" remote set-url origin "$LAB_ORIGIN"
else
  LAB_CURRENT_ORIGIN="$(git -C "$LAB_REPO" remote get-url origin 2>/dev/null || true)"
  case "$LAB_CURRENT_ORIGIN" in
    https://github.com/LamAnhProj/Microelectronic-layout.git|https://github.com/LamAnhProj/Microelectronic-layout|git@github.com:LamAnhProj/Microelectronic-layout.git) ;;
    '') git -C "$LAB_REPO" remote add origin "$LAB_ORIGIN" ;;
    *) echo 'Existing origin is a different repository; it has been preserved.' >&2; exit 1 ;;
  esac
fi

if ! gh auth status --hostname github.com >/dev/null 2>&1; then
  gh auth login --hostname github.com --git-protocol https --web
fi
LAB_LOGIN="$(gh api user --jq .login)"
if [[ "$LAB_LOGIN" != LamAnhProj ]]; then
  echo "Authenticated GitHub account is $LAB_LOGIN; this lab belongs to LamAnhProj." >&2
  echo 'Use gh auth switch --hostname github.com --user LamAnhProj, or sign in to that account.' >&2
  exit 1
fi
gh auth setup-git --hostname github.com

# Preserve an existing identity. Fill only missing values, in this repo only.
if ! git -C "$LAB_REPO" config --get user.name >/dev/null; then
  LAB_AUTHOR_NAME="$(gh api user --jq '.name // .login')"
  git -C "$LAB_REPO" config --local user.name "$LAB_AUTHOR_NAME"
fi
if ! git -C "$LAB_REPO" config --get user.email >/dev/null; then
  LAB_GITHUB_ID="$(gh api user --jq .id)"
  git -C "$LAB_REPO" config --local user.email "${LAB_GITHUB_ID}+${LAB_LOGIN}@users.noreply.github.com"
fi

git -C "$LAB_REPO" fetch origin master
# Preserve both histories; stop for a real conflict rather than force-pushing.
git -C "$LAB_REPO" merge --no-edit origin/master
git -C "$LAB_REPO" push --set-upstream origin master
git -C "$LAB_REPO" status --short --branch
echo "Git setup and publication complete. Working repository: $LAB_REPO"
echo "Next: cd \"$LAB_REPO\" && bash scripts/bootstrap-macos.sh"
