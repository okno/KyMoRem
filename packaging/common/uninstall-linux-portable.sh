#!/usr/bin/env bash
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
echo "KyMoRem portable uninstall"
echo "Folder: $HERE"

remove_portable_dir() {
  case "$(basename "$HERE")" in
    *KyMoRem*|*kymorem*)
      cd /
      rm -rf -- "$HERE"
      ;;
    *)
      echo "Refusing to remove unexpected portable folder: $HERE" >&2
      exit 1
      ;;
  esac
}

pkill -f "kymorem-agent" >/dev/null 2>&1 || true

if [[ "${1:-}" != "--force" ]]; then
  read -r -p "Delete this portable KyMoRem folder? Type YES: " answer
  if [[ "$answer" != "YES" ]]; then
    echo "Cancelled."
    exit 0
  fi
fi

remove_portable_dir
