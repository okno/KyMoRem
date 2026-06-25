# Changelog

## 0.2.0-rc1

Release candidate for the Windows host to Linux X11 client path.

### Added

- Sanitized README screenshot for the RC1 routing console.
- Direct Windows client mode through `KyMoRem.exe --client`.
- Client wake guard for Linux X11 and direct Windows clients: active listeners
  inhibit idle/sleep where supported and wake displays before remote input.
- Proportional pointer entry on the destination display.
- Input queue for remote keyboard, mouse button and wheel forwarding.
- Active input tracking on clients for safer release handling.
- Refreshed IT, EN and CH quick-start documentation.

### Changed

- Default runtime theme for new installs is `old_school_x11`.
- Runtime language switching now rebuilds the UI immediately and shows clean
  language labels: `Italiano`, `English`, `Swiss`.
- The README screenshot is loaded from root `screenshot.png`.
- Edge routing activates only when a client is configured for that side.
- Windows mouse movement is no longer suppressed while remote control is active;
  movement is converted to remote delta frames by the control loop.
- Linux release handling clears only active inputs plus safety modifiers instead
  of sending broad key-up sweeps.

### Verified

- Windows host to Linux X11 mouse movement after edge crossing.
- X11 key events for Shift, letter and function-key routing.
- X11 button press/release events.
- `Ctrl+Esc` emergency release.

## 0.1.1

Security and identity hardening release.

### Added

- UI byline: `by Pawel Zorzan Urban AKA okno`.
- Technical identity documentation for `KyMoRem`, `Keyboard Mouse Remote` and
  `KMR` casing.
- `KMR` favicon/icon mark and updated runtime PNG/ICO assets.
- Barrier field issue review based on public failure modes.
- Ten-cycle security review report.

### Security

- Refuse the development default token unless explicitly allowed for tests.
- Enforce minimum token length.
- Add max frame size enforcement for JSON and handshake frames.
- Add secure-frame replay and out-of-order sequence rejection.
- Use constant-time proof and token-id checks.
- Use HMAC-derived token ids instead of raw SHA-256 prefixes.
- Avoid public resolver references for local IP hints.
- Kill only stale KyMoRem-owned port processes at runtime.
- Harden SMTP relay header handling and STARTTLS context.
- Move Linux PID/log files to a per-user runtime directory.
- Release local control automatically when the secure link disconnects.
- Stop connection retry loops when the token is invalid.

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
