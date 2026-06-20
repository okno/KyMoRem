# KyMoRem Android

Android is a first-class KyMoRem target, but its permissions model is different
from desktop operating systems.

## MVP

The Android MVP should be an app-local remote surface:

- Discover or manually enter a host.
- Pair with a token.
- Receive pointer/key frames.
- Render a pointer inside the app.
- Send screen and capability metadata.

This proves latency, pairing, reconnects, and protocol compatibility.

## Later System Control

System-wide Android control requires one of:

- AccessibilityService for gestures and focused text fields.
- Device-owner mode for managed devices.
- Optional advanced bridge for power users.

## Suggested Stack

- Kotlin.
- Jetpack Compose.
- OkHttp or Ktor client for TCP/WebSocket adapter.
- Shared protocol generated from `docs/protocol.md` or mirrored data classes.

Keep Android protocol structs names aligned with `kymorem-protocol`.
