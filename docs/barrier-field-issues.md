# Barrier Field Issue Review

This document records public Barrier failure modes that influenced KyMoRem
hardening. It is not a compatibility promise and no Barrier source code is used.

## Reviewed Sources

| Field issue | Public source | KyMoRem response |
| --- | --- | --- |
| Client or server stuck at `Barrier is starting`; logs missing or not created | [Barrier #1922](https://github.com/debauchee/barrier/issues/1922), [Barrier #1836](https://github.com/debauchee/barrier/issues/1836), [Barrier #2022](https://github.com/debauchee/barrier/issues/2022) | Client launch kills stale KyMoRem PID and frees `54865/tcp` plus `54866/udp` only when owned by KyMoRem; logs are written to the per-user runtime directory; the secure pulse test validates the full path instead of relying on a static UI state. |
| SSL certificate or fingerprint missing after install | [Barrier #2076](https://github.com/debauchee/barrier/issues/2076), [Barrier #1377](https://github.com/debauchee/barrier/issues/1377), [Barrier discussion #1682](https://github.com/debauchee/barrier/discussions/1682) | KyMoRem does not require user-generated PEM files. Session keys are negotiated at runtime through ML-KEM/PSK-HKDF and AES-GCM. The selected suite is logged. |
| Wayland client appears to run but cannot inject input | [Barrier #109](https://github.com/debauchee/barrier/issues/109), [Barrier #247](https://github.com/debauchee/barrier/issues/247), [Fedora discussion](https://discussion.fedoraproject.org/t/barrier-under-wayland/80272) | The Linux client detects `XDG_SESSION_TYPE=wayland` and exits with a direct diagnostic unless `KYMOREM_ALLOW_WAYLAND=1` is set for experiments. The documented supported target is X11. |
| Clipboard stops working after extended use or large payloads lock input | [Barrier #103](https://github.com/debauchee/barrier/issues/103), [Barrier #775](https://github.com/debauchee/barrier/issues/775), [Barrier #2104](https://github.com/debauchee/barrier/issues/2104) | Clipboard sync is disabled by default, explicitly configured under `clipboard`, text-only by design for the first safe implementation, and bounded by `max_bytes`. |
| Auto discovery depends on Bonjour/Avahi behavior and can confuse diagnosis | [Fedora discussion](https://discussion.fedoraproject.org/t/barrier-under-wayland/80272) | KyMoRem uses token-protected UDP discovery with manual IP fallback. It does not call `DNSServiceRegister()` or require Avahi compatibility shims. |

## Design Decisions

### No Silent Start State

KyMoRem should never leave the operator with only a vague "starting" state. The
client preflight checks:

- stale PID;
- occupied TCP/UDP sockets;
- X11 tool availability;
- Wayland session type;
- crypto provider availability.

Failures go to stdout and the per-user runtime log:

```bash
${KYMOREM_RUNTIME_DIR:-${XDG_RUNTIME_DIR:-/tmp/kymorem-$UID}}/kymorem-client.log
```

### No Certificate Bootstrap Trap

Certificate files are not required for the Python MVP. The security boundary is
the shared deployment token plus per-session key derivation. Post-quantum mode
uses ML-KEM-768 when `pqcrypto` exists on both peers; otherwise encrypted PSK
fallback is selected and logged.

### Clipboard Is Explicitly Opt-In

KyMoRem treats clipboard as data transfer, not as input routing. The default is:

```json
{
  "clipboard": {
    "enabled": false,
    "max_bytes": 1048576,
    "text_only": true
  }
}
```

Large binary clipboard payloads must not block pointer or keyboard control.

### X11 First, Wayland Honest

The Linux input backend is X11. Wayland support requires compositor-specific
APIs or portals and must not be presented as working before it is implemented.
