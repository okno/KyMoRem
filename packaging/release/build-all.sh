#!/usr/bin/env bash
set -euo pipefail

VERSION="${VERSION:-0.1.1}"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
export VERSION

cd "$ROOT"

case "$(uname -s)" in
  Linux)
    bash packaging/linux/build-linux.sh
    bash packaging/android/build-android.sh || echo "Android build skipped or failed; see Android SDK setup."
    ;;
  Darwin)
    bash packaging/macos/build-macos.sh
    bash packaging/android/build-android.sh || echo "Android build skipped or failed; see Android SDK setup."
    ;;
  *)
    echo "Use packaging/release/build-all.ps1 on Windows."
    exit 1
    ;;
esac

if command -v shasum >/dev/null 2>&1; then
  (cd "$ROOT/artifacts" && shasum -a 256 * > SHA256SUMS.txt)
elif command -v sha256sum >/dev/null 2>&1; then
  (cd "$ROOT/artifacts" && sha256sum * > SHA256SUMS.txt)
fi

echo "Release tasks complete for $VERSION"
