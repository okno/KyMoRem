# Changelog

## 0.1.0

Initial public technical seed.

### Added

- Windows x64 host with Cyber Noir UI.
- Windows system tray with open, connect, take control, release and exit.
- Linux X11 client using `xdotool`.
- Linux tray using `yad`.
- Right-edge routing model.
- Secure TCP JSON-line protocol for the Python MVP.
- AES-256-GCM application-frame encryption.
- ML-KEM-768 hybrid key establishment when `pqcrypto` is available.
- PSK-HKDF-SHA256 encrypted fallback mode.
- Encrypted UDP LAN discovery on `54866/udp`.
- Optional SMTP email relay for operational events.
- IT, EN and CH localization slots only.
- Rust workspace for protocol/core/input/agent evolution.
- Android app shell.
- Windows standalone executable, setup executable and uninstaller.
- Linux `.deb`, portable archive and standalone daemon/test package.
- Debugging, FAQ, security, protocol, operations and platform documentation.

### Known Limits

- Linux input injection targets X11, not Wayland.
- macOS and Android are scaffolded but not release-grade.
- Windows 32-bit and Linux 32-bit release artifacts are planned but not built in
  this seed.
- PQ security depends on the optional `pqcrypto` provider being present on both
  peers; otherwise KyMoRem uses encrypted PSK fallback mode.
