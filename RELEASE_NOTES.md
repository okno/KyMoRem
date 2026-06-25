# KyMoRem v0.2.0-rc1

KyMoRem v0.2.0-rc1 is the first release candidate for the Windows host to Linux
X11 client runtime.

## Highlights

- Edge routing is now configuration-aware: unassigned screen sides do not take
  remote control.
- Pointer entry is proportional to the destination display resolution.
- Active clients inhibit idle/sleep where supported and wake the display before
  remote mouse or keyboard input is injected.
- Windows host mouse movement remains live while remote control is active.
- Keyboard, mouse buttons and wheel are captured, queued and forwarded to the
  active client without leaking local input to the host.
- `Ctrl+Esc` releases control and clears active remote input state.
- Linux X11 client tracks active keys/buttons and releases only active inputs
  plus safety modifiers.
- Direct Windows client mode is available with `KyMoRem.exe --client`.
- Default runtime theme for new installs is `old_school_x11`.
- README now includes a sanitized RC1 screenshot.
- Runtime language switching updates the UI immediately and uses clean display
  labels: `Italiano`, `English`, `Swiss`.
- IT, EN and CH quick-start documentation has been refreshed.

## Verified RC Path

- Windows host application starts as `0.2.0-rc1`.
- Linux X11 client accepts the secure session on `54865/tcp`.
- Mouse movement is delivered after crossing the configured edge.
- Shift/key combinations are delivered as X11 key press/release events.
- Mouse button press/release is delivered as X11 button events.
- Emergency release returns control to the host.

## Release Assets

Planned artifact names:

- `KyMoRem-0.2.0-rc1-windows-x64.exe`
- `KyMoRem-0.2.0-rc1-windows-x64-setup.exe`
- `KyMoRem-0.2.0-rc1-windows-x64-uninstall.exe`
- `KyMoRem-0.2.0-rc1-windows-x64-portable.zip`
- `KyMoRem-0.2.0-rc1-linux-x64.deb`
- `KyMoRem-0.2.0-rc1-linux-x64-portable.tar.gz`
- `KyMoRem-0.2.0-rc1-linux-x64-portable.zip`
- `KyMoRem-0.2.0-rc1-linux-x64-standalone.tar.gz`
- `KyMoRem-0.2.0-rc1-linux-x64-standalone.zip`
- `SHA256SUMS.txt`

## Security Notice

Set a strong deployment token on both host and client. KyMoRem refuses the
development placeholder token unless `KYMOREM_ALLOW_DEFAULT_TOKEN=1` is set for
local diagnostics. Keep `54865/tcp` and `54866/udp` limited to trusted LAN
segments.
