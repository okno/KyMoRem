# KyMoRem

KyMoRem, Keyboard Mouse Remote, is a LAN-first keyboard and pointer sharing
system for desktop machines and external devices. The host owns the physical
keyboard and mouse; clients receive secured input frames and inject them into
their local graphical session.

The current release focuses on a practical Windows host to Linux X11 client
path, with a Cyber Noir UI, system tray integration, encrypted transport,
LAN autodiscovery, standalone Linux test packaging, and release artifacts.

KyMoRem follows the screen-edge workflow used by KVM tools such as Barrier, but
it does not copy Barrier source code and does not implement the Barrier/Synergy
wire protocol.

## Current Release

`v0.1.1` is a technical seed release.

Implemented:

- Windows x64 host application with Cyber Noir control console.
- Windows system tray: open, connect, take control, release, exit.
- Linux x64 X11 client using `xdotool`.
- Linux tray using `yad`.
- Linux standalone package for tests and user-level daemon deployment.
- Right-edge routing and emergency release with `Ctrl+Esc`.
- Encrypted TCP session using AES-256-GCM.
- Hybrid key establishment with ML-KEM-768 when the PQ provider is available.
- Token-protected UDP LAN discovery on `54866/udp`.
- Optional SMTP email relay for operational events.
- Official localization slots: IT, EN, CH.

Scaffolded:

- Rust protocol/core/agent workspace.
- Android app shell.
- macOS packaging templates.
- Windows MSI/Inno packaging recipes.
- Linux DEB and portable packaging recipes.

## Quick Start

Windows host:

1. Install `KyMoRem-0.1.1-windows-x64-setup.exe`.
2. Open `%APPDATA%\KyMoRem\config.json`.
3. Set a long shared `token`. The development placeholder token is refused by
   default.
4. Start KyMoRem. Discovery can select the first compatible client
   automatically.

Linux client:

```bash
tar -xzf KyMoRem-0.1.1-linux-x64-standalone.tar.gz
cd KyMoRem
export KYMOREM_TOKEN="use-a-long-shared-token"
./run-client.sh
```

Secure pulse test:

```bash
export KYMOREM_TOKEN="use-a-long-shared-token"
./run-test.sh 127.0.0.1 54865
```

User daemon:

```bash
./install-daemon.sh
nano ~/.config/kymorem/kymorem.env
systemctl --user restart kymorem-client.service
systemctl --user status kymorem-client.service
```

## Network Model

```text
Windows host                  Linux client
UI + physical input      ->   X11 input injection
UDP discovery 54866      ->   encrypted signed announcement
TCP session 54865        ->   secure input/control channel
right screen edge        ->   remote control active
Ctrl+Esc or left edge    ->   release control
```

## Repository Layout

```text
runtime/python/              Working Windows/Linux MVP
crates/kymorem-protocol/     Rust protocol structs and codec
crates/kymorem-core/         Rust layout/routing primitives
crates/kymorem-input/        Rust input abstraction
apps/kymorem-agent/          Rust CLI agent prototype
apps/android/                Android shell
install/                     Practical install scripts
packaging/                   Release packaging recipes
docs/                        Technical and operational documentation
assets/themes/               Theme tokens
```

## Documentation

- [Architecture](docs/architecture.md)
- [Service Design](docs/service.md)
- [Configuration](docs/configuration.md)
- [Networking](docs/networking.md)
- [Protocol](docs/protocol.md)
- [Cryptography](docs/cryptography.md)
- [LAN Discovery](docs/discovery.md)
- [Barrier Field Issue Review](docs/barrier-field-issues.md)
- [Operations](docs/operations.md)
- [Email Relay](docs/email-relay.md)
- [Localization](docs/localization.md)
- [Tray Integration](docs/tray.md)
- [Technical Identity](docs/technical-identity.md)
- [Themes](docs/themes.md)
- [Debugging](DEBUGGING.md)
- [FAQ](FAQ.md)
- [Security](SECURITY.md)
- [Security Review 2026-06-20](docs/security-review-2026-06-20.md)
- [Release Process](docs/release.md)

## Security Notice

KyMoRem controls local input. Deploy it only on networks where device access,
firewall policy and token distribution are managed. Replace the development
token before use. KyMoRem refuses the placeholder token unless
`KYMOREM_ALLOW_DEFAULT_TOKEN=1` is set for diagnostics. Do not expose
`54865/tcp` or `54866/udp` to untrusted networks.

## License

MIT.
