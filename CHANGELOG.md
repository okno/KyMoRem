# Changelog

## 0.2.0-rc1

Release candidate for the Windows host to Linux X11 client path.

### Added

- Sanitized README screenshot for the RC1 routing console.
- Direct Windows client mode through `KyMoRem.exe --client`.
- Proportional pointer entry on the destination display.
- Input queue for remote keyboard, mouse button and wheel forwarding.
- Active input tracking on clients for safer release handling.
- Refreshed IT, EN and CH quick-start documentation.

### Changed

- Default runtime theme for new installs is `old_school_x11`.
- Runtime language switching now rebuilds the UI immediately and shows clean
  language labels: `Italiano`, `English`, `Swiss`.
- The README screenshot is loaded from root `screenshot.png`.
- Diagonal client placements such as bottom-left now expose both active edges
  and the take-control command uses the selected client instead of the old
  right-edge default.
- Position selection now preserves the interactive `x,y` layout model; saving
  host/name/port no longer collapses a dragged diagonal client into a single
  cardinal side.
- Linux X11 pointer motion now uses tracked absolute coordinates instead of
  blind relative deltas, preventing pointer stalls at monitor edges.
- Linux X11 client focuses the window under the pointer when remote control
  enters the display, so keyboard modifiers and combinations route to the
  remote desktop.
- Linux client connection resets are logged cleanly instead of leaking traceback
  noise or stale active sessions.
- Global edge routing is ignored while the pointer is over the KyMoRem UI, so
  menus and window controls remain usable while the server is armed.
- Host edge detection now activates from an inset band before the physical last
  pixel and suppresses hot-corner activation zones to avoid Windows corner UI.
- Host edge detection uses the full virtual desktop rectangle on Windows, so
  multi-monitor coordinates no longer trigger phantom edges at monitor seams.
- Remote mouse movement and wheel input are coalesced at a bounded frame rate;
  high-resolution wheel bursts no longer create unbounded network/input queues.
- Remote wheel input now has a bounded pending backlog and preserves partial
  wheel deltas until a real 120-unit wheel step is available.
- Horizontal wheel input is forwarded separately on Linux X11 and Windows
  clients for high-end mice with side scroll.
- Pending edge takeover requests expire and are cancelled if the pointer leaves
  the originating edge before the encrypted client handshake completes.
- Pending takeover now also verifies that the encrypted socket endpoint matches
  the selected client, preventing stale connection races from taking control on
  the wrong client.
- Windows client pointer entry and return-edge reporting now use the virtual
  desktop rectangle instead of primary-monitor metrics.
- Clients report all active edges at display corners, so returning from diagonal
  layouts does not get blocked by left/right priority.
- Linux and Windows clients cap remote wheel batches; the Linux X11 client uses
  one `xdotool click --repeat N` call per wheel batch instead of one subprocess
  per wheel tick.
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
- Automated regression tests for diagonal edge routing and Linux absolute
  pointer clamping.
- Direct smoke tests against the installed `linux-iMac` client for ML-KEM
  handshake, pointer enter/move/locate/release and modifier key release.
- Automated regression tests for Windows hot-corner suppression and Logitech
  G502-style wheel burst coalescing.
- Automated regression tests for virtual desktop edge routing, stale pending
  takeover cancellation, horizontal wheel forwarding and sub-step wheel
  remainder preservation.
- Automated regression tests for wrong-endpoint takeover rejection, Windows
  virtual-screen client edges, Windows whole-step wheel clamping and client
  corner return-edge reporting.
- Windows 7 x86/x64 client executables with encrypted transport smoke-tested on
  localhost.
- Android release APKs for arm64-v8a, armeabi-v7a, x86, x86_64, universal APK
  and release AAB built with local portable JDK/Gradle/Android SDK.

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
