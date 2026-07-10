# KyMoRem v0.2.0-rc2 "Super Route"

KyMoRem v0.2.0-rc2 is the Super Route release for the Windows host, Linux X11
client and Windows 7 client workflow.

## Highlights

- Server route map now supports practical multi-client placement and refresh.
- Client layout can be edited on the server, saved, refreshed and used for the
  next route decision.
- Windows 7 x86/x64 onboarding is package-driven: token generation, server
  approval, firewall setup and restart scripts are created together.
- Pending clients can be pre-approved with `host=pending`; the first valid
  discovery packet fills the real IP address.
- Switching between Linux and Windows 7 endpoints now disconnects the old
  remote link before opening the new one.
- Infinite-scroll and high-resolution wheel bursts are coalesced and capped.
- Discovery counts now distinguish online inventory from pending/offline state.
- Unknown discovery clients are saved disabled unless `auto_approve` is
  explicitly enabled.
- Official brand assets were added under `assets/brand`.
- README and localized FAQs now include the real failure modes found during
  testing, including Windows 7 handshake, discovery, layout refresh, return edge
  and infinite-scroll recovery.

## Verified RC Path

- Windows host application starts as `0.2.0-rc2`.
- Linux X11 client accepts secure ML-KEM/PSK sessions on `54865/tcp`.
- Windows 7 client accepts PSK/HKDF AES-256-GCM sessions on `54865/tcp`.
- Server can switch from Linux client to Windows 7 client without retaining a
  stale input endpoint.
- Return edge and `Ctrl+Esc` release control and clear queued input.
- Gamer mouse wheel bursts do not create unbounded client queues.
- Regression suite `tests.test_kymorem_routing` passes.

## Release Assets

Planned artifact names:

- `KyMoRem-0.2.0-rc2-windows-x64.exe`
- `KyMoRem-0.2.0-rc2-windows-x64-setup.exe`
- `KyMoRem-0.2.0-rc2-windows-x64-uninstall.exe`
- `KyMoRem-0.2.0-rc2-windows-x64-portable.zip`
- `KyMoRem-0.2.0-rc2-windows7-x86-client.exe`
- `KyMoRem-0.2.0-rc2-windows7-x64-client.exe`
- `KyMoRem-0.2.0-rc2-linux-x64.deb`
- `KyMoRem-0.2.0-rc2-linux-x64-portable.tar.gz`
- `KyMoRem-0.2.0-rc2-linux-x64-portable.zip`
- `KyMoRem-0.2.0-rc2-linux-x64-standalone.tar.gz`
- `KyMoRem-0.2.0-rc2-linux-x64-standalone.zip`
- `SHA256SUMS.txt`

## Security Notice

Set a strong deployment token on the server. The Windows 7 package generator
creates one automatically when the server token is missing, weak or still the
development placeholder. Keep `kymorem-token.txt`, `kymorem.env` and the server
config private. Do not expose `54865/tcp` or `54866/udp` to unmanaged networks.
