# KyMoRem v0.1.1

KyMoRem v0.1.1 is the security and identity hardening release.

Highlights:

- Windows UI header now shows `KyMoRem` with `by Pawel Zorzan Urban AKA okno`.
- Favicon/icon assets use the uppercase `KMR` mark.
- Product metadata documents `KyMoRem`, `Keyboard Mouse Remote` and `KMR`
  casing.
- Public Barrier issue review added with KyMoRem countermeasures.
- Ten-cycle security review completed and documented.
- Default development token is refused unless explicitly allowed for tests.
- Secure frames now enforce maximum size, suite match and monotonic sequence.
- Handshake proof checks use constant-time comparison.
- Runtime port cleanup kills only KyMoRem-owned processes.
- Linux PID/log files moved to a per-user runtime directory.
- Windows host releases local control automatically if the secure link drops.

## Release Assets

- `KyMoRem-0.1.1-windows-x64.exe`
- `KyMoRem-0.1.1-windows-x64-setup.exe`
- `KyMoRem-0.1.1-windows-x64-uninstall.exe`
- `KyMoRem-0.1.1-windows-x64-portable.zip`
- `KyMoRem-0.1.1-linux-x64.deb`
- `KyMoRem-0.1.1-linux-x64-portable.tar.gz`
- `KyMoRem-0.1.1-linux-x64-portable.zip`
- `KyMoRem-0.1.1-linux-x64-standalone.tar.gz`
- `KyMoRem-0.1.1-linux-x64-standalone.zip`
- `SHA256SUMS.txt`

## Security Notice

Set a strong deployment token on both host and client. KyMoRem refuses the
development placeholder token unless `KYMOREM_ALLOW_DEFAULT_TOKEN=1` is set for
local diagnostics.
