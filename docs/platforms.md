# Platform Notes

## Windows

Target native backend:

- `SendInput` for keyboard, mouse, wheel.
- Optional raw input hook on the host side.
- Tray app or Windows service can be added later.

Security and permissions:

- Some elevated applications ignore events from non-elevated processes.
- A production agent may need matching integrity level or a service bridge.

## macOS

Target native backend:

- `CGEventPost` for input.
- Event tap for host capture.

Security and permissions:

- Accessibility permission is required.
- Input Monitoring permission may be required for capture.
- The app bundle must explain these permissions clearly.

## Linux

Target native backend:

- X11: XTest for injection and XInput2 for capture.
- Wayland: compositor portals or compositor-specific protocols.

Security and permissions:

- Wayland intentionally blocks global input injection in many environments.
- The first reliable Linux backend should target X11, then add Wayland paths.

## Android

Target native backend options:

- App-local remote surface: simple and safe. Pointer only exists inside KyMoRem.
- AccessibilityService: can perform gestures and some text actions.
- Device-owner / managed profile: more powerful, not normal consumer setup.
- Root/Shizuku style bridge: powerful but optional and not baseline.

The Android MVP should start as an app-local device so pairing, latency, and UI
can be tested without special privileges.
