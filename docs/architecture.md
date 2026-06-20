# Architecture

KyMoRem is split into transport-independent core pieces and thin platform
adapters.

## Goals

- Share one keyboard and pointer across desktop machines and external devices.
- Prefer same-LAN operation with explicit token-based trust.
- Keep Android and macOS as first-class target platforms.
- Keep the protocol inspectable while enforcing encrypted transport.
- Preserve the useful screen-edge workflow without copying Barrier internals.

## Components

```text
physical input
    |
    v
host UI -> layout router -> secure transport -> client agent -> input backend
              |                    ^
              v                    |
        encrypted discovery --------
```

## Host Agent

The host runs on the machine that owns the physical keyboard and mouse.

Responsibilities:

- maintain UI and tray;
- listen for encrypted discovery announcements;
- select a right-side client from configuration or discovery;
- negotiate the secure transport;
- detect screen-edge exits;
- stream input frames;
- provide local emergency release;
- emit optional operational notifications.

## Client Agent

The client runs on a target machine or external device.

Responsibilities:

- announce role and capabilities through encrypted discovery;
- accept secure host sessions;
- report screen size and platform capabilities;
- dispatch pointer and key events through the platform backend;
- report edge return events.

## Runtime MVP

The current working path is Python:

- Windows: Tkinter host UI plus Win32 input polling.
- Linux: X11 target using `xdotool`.
- Transport: secure JSON frames over TCP.
- Discovery: encrypted UDP broadcast.

## Rust Workspace

The Rust crates define the long-term native agent shape:

- `kymorem-protocol`: wire frames and compatibility rules.
- `kymorem-core`: layout and routing decisions.
- `kymorem-input`: platform input abstraction.
- `kymorem-agent`: CLI prototype.

## Platform Backends

Planned native backends:

- Windows: SendInput.
- macOS: CGEvent and Accessibility permissions.
- Linux X11: XTest.
- Linux Wayland: compositor portal where available.
- Android: AccessibilityService or app-local pointer surface.

## Difference From Barrier

Barrier is a mature C++/Qt application with its own protocol and platform
history. KyMoRem keeps the familiar user model but uses a new protocol,
security layer, discovery mechanism and package structure.
