#!/usr/bin/env bash
set -euo pipefail

VERSION="${VERSION:-0.1.1}"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
ARTIFACTS="$ROOT/artifacts"
DIST_ROOT="$ROOT/dist/macos"
APP_TEMPLATE="$ROOT/packaging/macos/KyMoRem.app.template"
if [[ $# -gt 0 ]]; then
  ARCHES=("$@")
else
  ARCHES=(x64 arm64)
fi

require() {
  if ! command -v "$1" >/dev/null 2>&1; then
    echo "$1 not found. $2" >&2
    exit 1
  fi
}

cargo_target() {
  case "$1" in
    x64) echo "x86_64-apple-darwin" ;;
    arm64) echo "aarch64-apple-darwin" ;;
    *) echo "Unsupported architecture: $1" >&2; exit 1 ;;
  esac
}

copy_app() {
  local arch="$1"
  local target="$2"
  local app="$DIST_ROOT/$arch/KyMoRem.app"
  local binary="$ROOT/target/$target/release/kymorem-agent"

  if [[ ! -x "$binary" ]]; then
    echo "Missing compiled binary: $binary" >&2
    exit 1
  fi

  rm -rf "$app"
  mkdir -p "$app"
  cp -R "$APP_TEMPLATE/Contents" "$app/"
  mkdir -p "$app/Contents/MacOS" "$app/Contents/Resources"
  install -m 0755 "$binary" "$app/Contents/MacOS/kymorem-agent"
  cp -R "$ROOT/assets" "$app/Contents/Resources/assets"
  cp -R "$ROOT/packaging/i18n" "$app/Contents/Resources/i18n"
  install -m 0644 "$ROOT/packaging/common/product.json" "$app/Contents/Resources/product.json"
  install -m 0644 "$ROOT/README.md" "$app/Contents/Resources/README.md"
  install -m 0644 "$ROOT/LICENSE" "$app/Contents/Resources/LICENSE"
  install -m 0755 "$ROOT/packaging/macos/uninstall.sh" "$app/Contents/Resources/uninstall.sh"
  cp -R "$ROOT/packaging/macos/lproj/." "$app/Contents/Resources/"
  sed -i '' "s/@VERSION@/$VERSION/g" "$app/Contents/Info.plist"
}

package_app() {
  local arch="$1"
  local app="$DIST_ROOT/$arch/KyMoRem.app"
  local pkg="$ARTIFACTS/KyMoRem-$VERSION-macos-$arch.pkg"
  local dmg="$ARTIFACTS/KyMoRem-$VERSION-macos-$arch.dmg"

  pkgbuild \
    --component "$app" \
    --install-location /Applications \
    --identifier "dev.kymorem.agent.$arch" \
    --version "$VERSION" \
    "$pkg"

  rm -f "$dmg"
  hdiutil create \
    -volname "KyMoRem $VERSION" \
    -srcfolder "$app" \
    -ov \
    -format UDZO \
    "$dmg"
}

require cargo "Install Rust from https://rustup.rs"
require rustup "Install rustup from https://rustup.rs"
require pkgbuild "Run on macOS with Xcode Command Line Tools."
require hdiutil "Run on macOS."

mkdir -p "$ARTIFACTS" "$DIST_ROOT"

for arch in "${ARCHES[@]}"; do
  target="$(cargo_target "$arch")"
  echo "Building KyMoRem for macOS $arch ($target)"
  rustup target add "$target"
  cargo build --release --target "$target" -p kymorem-agent
  copy_app "$arch" "$target"
  package_app "$arch"
done

if [[ -d "$DIST_ROOT/x64/KyMoRem.app" && -d "$DIST_ROOT/arm64/KyMoRem.app" ]] && command -v lipo >/dev/null 2>&1; then
  universal="$DIST_ROOT/universal2/KyMoRem.app"
  rm -rf "$universal"
  mkdir -p "$(dirname "$universal")"
  cp -R "$DIST_ROOT/x64/KyMoRem.app" "$universal"
  lipo -create \
    "$DIST_ROOT/x64/KyMoRem.app/Contents/MacOS/kymorem-agent" \
    "$DIST_ROOT/arm64/KyMoRem.app/Contents/MacOS/kymorem-agent" \
    -output "$universal/Contents/MacOS/kymorem-agent"
  package_app "universal2"
fi
