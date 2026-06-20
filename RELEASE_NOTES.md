# KyMoRem v0.1.0

KyMoRem v0.1.0 is the first public technical seed.

It provides a working Windows-to-Linux LAN input routing path:

- Windows x64 host with Cyber Noir UI.
- Windows system tray.
- Linux X11 client.
- Linux tray and standalone daemon/test package.
- Right-edge routing from host to client.
- Release path through `Ctrl+Esc` or left-edge return.
- Secure TCP session with AES-256-GCM.
- ML-KEM-768 hybrid key establishment when the PQ provider is available.
- Encrypted token-protected UDP discovery.
- Optional SMTP operational email relay.
- IT, EN and CH localization only.

## Release Assets

- `KyMoRem-0.1.0-windows-x64.exe`
- `KyMoRem-0.1.0-windows-x64-setup.exe`
- `KyMoRem-0.1.0-windows-x64-uninstall.exe`
- `KyMoRem-0.1.0-windows-x64-portable.zip`
- `KyMoRem-0.1.0-linux-x64.deb`
- `KyMoRem-0.1.0-linux-x64-portable.tar.gz`
- `KyMoRem-0.1.0-linux-x64-portable.zip`
- `KyMoRem-0.1.0-linux-x64-standalone.tar.gz`
- `KyMoRem-0.1.0-linux-x64-standalone.zip`
- `SHA256SUMS.txt`

## Security Notice

Replace the default token before deployment. Keep `54865/tcp` and `54866/udp`
inside trusted LAN segments. PQ mode requires `pqcrypto` on both peers;
otherwise the release uses the encrypted PSK-HKDF fallback.
