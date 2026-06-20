#!/usr/bin/env bash
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
echo "KyMoRem portable uninstall"
echo "Folder: $HERE"

pkill -f "kymorem-agent" >/dev/null 2>&1 || true

if [[ "${1:-}" != "--force" ]]; then
  read -r -p "Delete this portable KyMoRem folder? Type YES: " answer
  if [[ "$answer" != "YES" ]]; then
    echo "Cancelled."
    exit 0
  fi
fi

cd /
rm -rf "$HERE"
