# KyMoRem FAQ

## What is KyMoRem?

KyMoRem is a LAN keyboard and mouse remote-control system. One host machine
owns the physical input devices; one or more clients receive encrypted pointer,
button, wheel and key frames.

## Is KyMoRem compatible with Barrier?

No. KyMoRem uses a similar screen-edge workflow but has its own implementation,
protocol, discovery layer and security model.

## Which Barrier pain points does KyMoRem address?

KyMoRem was hardened against common public Barrier failure modes: vague
"starting" loops, missing SSL certificate bootstrap, Wayland clients that appear
to run but cannot inject input, clipboard stalls, and Bonjour/Avahi discovery
confusion. The technical matrix is in
[docs/barrier-field-issues.md](docs/barrier-field-issues.md).

## Which platforms work today?

Release-grade path in v0.2.0-rc1:

- Windows x64 host with Cyber Noir UI and system tray.
- Linux x64 X11 client with `xdotool` input injection.
- Linux standalone package for manual tests and user-level daemon install.

Scaffolded targets:

- macOS packaging.
- Android app shell.
- Rust native agent.

## Is the transport encrypted?

Yes. The TCP input channel is encrypted with AES-256-GCM. The preferred key
establishment suite uses ML-KEM-768 plus the shared token when the optional PQ
provider is available. If not, KyMoRem logs and uses the PSK-HKDF fallback.

## What does discovery do?

Discovery broadcasts encrypted endpoint announcements on `54866/udp`. The host
can classify endpoints as host or client and autoconnect to the first valid
client when the configured host is still the loopback placeholder.

## Why does Linux run as a user service?

Input injection needs access to the active X11 session. A system service often
does not have `DISPLAY`, `XAUTHORITY` or the user DBus session.

## Does Wayland work?

Not as a full input-injection target in v0.2.0-rc1. Wayland blocks global input
injection in many compositors. The Linux client detects Wayland and exits with a
clear diagnostic unless an explicit diagnostic override is set.

## How do I exit remote control mode?

Use either:

- move the pointer to the left edge on the Linux client;
- press `Ctrl+Esc` on the Windows host.

## Where are logs?

Windows:

```text
%APPDATA%\KyMoRem\server.log
```

Linux:

```text
${XDG_RUNTIME_DIR:-/tmp/kymorem-$UID}/kymorem-client.log
${XDG_RUNTIME_DIR:-/tmp/kymorem-$UID}/kymorem-tray.log
/tmp/kymorem-tray.launch.log
```

## Which languages are included?

Only IT, EN and CH are included in v0.2.0-rc1 runtime strings, packaging metadata
and localized documentation.
