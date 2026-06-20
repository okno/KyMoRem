#!/usr/bin/env bash
set -euo pipefail

VERSION="${VERSION:-0.2.0-rc1}"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
ARTIFACTS="$ROOT/artifacts"
DIST_ROOT="$ROOT/dist/linux"
STAGE_ROOT="$ROOT/target/package/linux"

if [[ $# -gt 0 ]]; then
  ARCHES=("$@")
else
  ARCHES=(x64 x86)
fi

require() {
  if ! command -v "$1" >/dev/null 2>&1; then
    echo "$1 not found. $2" >&2
    exit 1
  fi
}

cargo_target() {
  case "$1" in
    x64) echo "x86_64-unknown-linux-gnu" ;;
    x86) echo "i686-unknown-linux-gnu" ;;
    *) echo "Unsupported architecture: $1" >&2; exit 1 ;;
  esac
}

deb_arch() {
  case "$1" in
    x64) echo "amd64" ;;
    x86) echo "i386" ;;
    *) echo "Unsupported architecture: $1" >&2; exit 1 ;;
  esac
}

copy_payload() {
  local arch="$1"
  local target="$2"
  local dest="$3"
  local binary="$ROOT/target/$target/release/kymorem-agent"

  if [[ ! -x "$binary" ]]; then
    echo "Missing compiled binary: $binary" >&2
    exit 1
  fi

  rm -rf "$dest"
  mkdir -p "$dest/bin" "$dest/share"
  install -m 0755 "$binary" "$dest/bin/kymorem-agent"
  install -m 0644 "$ROOT/README.md" "$dest/README.md"
  install -m 0644 "$ROOT/LICENSE" "$dest/LICENSE"
  install -m 0755 "$ROOT/packaging/common/uninstall-linux-portable.sh" "$dest/uninstall.sh"
  cp -R "$ROOT/assets" "$dest/share/assets"
  cp -R "$ROOT/packaging/i18n" "$dest/share/i18n"
  install -m 0644 "$ROOT/packaging/common/product.json" "$dest/share/product.json"

  cat > "$dest/kymorem-host.sh" <<'EOF'
#!/usr/bin/env bash
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec "$DIR/bin/kymorem-agent" host --token "${KYMOREM_TOKEN:-kymorem-local-default-change-me}"
EOF
  chmod 0755 "$dest/kymorem-host.sh"

  cat > "$dest/kymorem-device-demo.sh" <<'EOF'
#!/usr/bin/env bash
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec "$DIR/bin/kymorem-agent" device --host "${KYMOREM_HOST:-127.0.0.1:54865}" --token "${KYMOREM_TOKEN:-kymorem-local-default-change-me}" --demo
EOF
  chmod 0755 "$dest/kymorem-device-demo.sh"
}

build_deb() {
  local arch="$1"
  local target="$2"
  local debarch
  debarch="$(deb_arch "$arch")"
  local pkg="$STAGE_ROOT/deb/kymorem_${VERSION}_${debarch}"

  rm -rf "$pkg"
  mkdir -p "$pkg/DEBIAN" "$pkg/usr/bin" "$pkg/usr/share/kymorem" "$pkg/usr/share/applications" "$pkg/usr/lib/systemd/user"

  install -m 0755 "$ROOT/target/$target/release/kymorem-agent" "$pkg/usr/bin/kymorem-agent"
  install -m 0644 "$ROOT/README.md" "$pkg/usr/share/kymorem/README.md"
  install -m 0644 "$ROOT/LICENSE" "$pkg/usr/share/kymorem/LICENSE"
  cp -R "$ROOT/assets" "$pkg/usr/share/kymorem/assets"
  cp -R "$ROOT/packaging/i18n" "$pkg/usr/share/kymorem/i18n"
  install -m 0644 "$ROOT/packaging/common/product.json" "$pkg/usr/share/kymorem/product.json"
  install -m 0644 "$ROOT/packaging/linux/kymorem.desktop" "$pkg/usr/share/applications/kymorem.desktop"
  install -m 0644 "$ROOT/packaging/linux/systemd/kymorem-host.service" "$pkg/usr/lib/systemd/user/kymorem-host.service"
  install -m 0755 "$ROOT/packaging/linux/deb/postinst" "$pkg/DEBIAN/postinst"
  install -m 0755 "$ROOT/packaging/linux/deb/prerm" "$pkg/DEBIAN/prerm"

  sed \
    -e "s/@VERSION@/$VERSION/g" \
    -e "s/@ARCH@/$debarch/g" \
    "$ROOT/packaging/linux/deb/control.template" > "$pkg/DEBIAN/control"

  fakeroot dpkg-deb --build "$pkg" "$ARTIFACTS/KyMoRem-$VERSION-linux-$arch.deb"
}

require cargo "Install Rust from https://rustup.rs"
require rustup "Install rustup from https://rustup.rs"
require tar "Install tar."
require dpkg-deb "Install dpkg-dev."
require fakeroot "Install fakeroot."

mkdir -p "$ARTIFACTS" "$DIST_ROOT" "$STAGE_ROOT"

for arch in "${ARCHES[@]}"; do
  target="$(cargo_target "$arch")"
  echo "Building KyMoRem for Linux $arch ($target)"
  rustup target add "$target"
  cargo build --release --target "$target" -p kymorem-agent

  portable="$DIST_ROOT/$arch/KyMoRem"
  copy_payload "$arch" "$target" "$portable"

  tar -C "$(dirname "$portable")" -czf "$ARTIFACTS/KyMoRem-$VERSION-linux-$arch-portable.tar.gz" "KyMoRem"
  if command -v zip >/dev/null 2>&1; then
    (cd "$(dirname "$portable")" && zip -qr "$ARTIFACTS/KyMoRem-$VERSION-linux-$arch-portable.zip" "KyMoRem")
  else
    echo "zip not found; skipped Linux portable zip"
  fi

  build_deb "$arch" "$target"
done
