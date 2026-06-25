# KyMoRem

KyMoRem, Keyboard Mouse Remote, is a LAN-first keyboard and pointer sharing
system for desktop machines and external devices. A host owns the physical
keyboard and mouse; clients receive authenticated, encrypted input frames and
inject them into their local graphical session.

KyMoRem follows the screen-edge workflow used by KVM tools such as Barrier, but
it does not copy Barrier source code and does not implement the Barrier/Synergy
wire protocol.

![KyMoRem RC1 routing console](screenshot.png)

## Release Candidate

`v0.2.0-rc1` is the first release candidate for the Python Windows-to-Linux
runtime.

RC1 focuses on the practical Windows host to Linux X11 client path:

- Windows host UI with the `KMR` routing map, system tray and themed controls.
- Linux X11 client with `xdotool` injection.
- Configurable client placement on left, right, up and down edges.
- Edge activation only when a client is configured for that side.
- Proportional pointer entry on the destination display.
- Remote mouse movement, buttons, wheel and keyboard modifiers.
- Client wake guard: running clients stay listening, inhibit idle/sleep where
  the OS allows it, and wake the display before injected mouse/keyboard input.
- Emergency release with `Ctrl+Esc`.
- Clipboard text sharing and bounded file transfer.
- Encrypted TCP session using AES-256-GCM.
- Hybrid ML-KEM-768 plus PSK key establishment when the PQ provider is
  available.
- Token-protected UDP LAN discovery on `54866/udp`.
- Linux standalone client package for tests and user-level daemon deployment.
- Official localization slots: IT, EN, CH.

Scaffolded targets are kept in the repository for continued work:

- Rust protocol/core/agent workspace.
- Android app shell.
- macOS packaging templates.
- Windows MSI/Inno packaging recipes.
- Linux DEB and portable packaging recipes.

## Quick Start

Windows host:

1. Install `KyMoRem-0.2.0-rc1-windows-x64-setup.exe`.
2. Open `%APPDATA%\KyMoRem\config.json`.
3. Set a long shared `token`. The development placeholder token is refused by
   default.
4. Start KyMoRem, switch to `Server`, enable `SERVER ON`, then place clients on
   the routing map.

Linux client:

```bash
tar -xzf KyMoRem-0.2.0-rc1-linux-x64-standalone.tar.gz
cd KyMoRem-linux-x64-standalone
export KYMOREM_TOKEN="use-a-long-shared-token"
./run-client.sh
```

Direct Windows client mode:

```powershell
KyMoRem.exe --client --bind 0.0.0.0 --port 54865 --name windows-client
```

Secure pulse test:

```bash
export KYMOREM_TOKEN="use-a-long-shared-token"
./run-test.sh 127.0.0.1 54865
```

User daemon on Linux:

```bash
./install-daemon.sh
nano ~/.config/kymorem/kymorem.env
systemctl --user restart kymorem-client.service
systemctl --user status kymorem-client.service
```

## Network Model

```text
Windows host                  Linux X11 client
UI + physical input      ->   X11 input injection
UDP discovery 54866      ->   encrypted LAN announcement
TCP session 54865        ->   secure input/control channel
right screen edge        ->   remote control active
Ctrl+Esc/client edge     ->   release control
```

Pointer routing is proportional. For example, leaving the right edge of the
host at 75 percent of screen height enters the left edge of the client at 75
percent of the client display height.

## Client Wake Guard

When a KyMoRem client is running, it is treated as an always-listening endpoint.
The Linux X11 client disables session blanking/DPMS, requests a systemd idle and
sleep inhibitor when available, and forces the display on before remote pointer
or keyboard input is injected. The direct Windows client calls
`SetThreadExecutionState` to keep the system and display required while the
listener is active.

This does not bypass operating-system lock screens, passwords, firmware sleep
states or Wake-on-LAN requirements. If the machine is already fully suspended at
hardware level, the network listener cannot run; configure firmware/OS wake
policy separately for that case.

## Repository Layout

```text
runtime/python/              Working Windows/Linux RC runtime
crates/kymorem-protocol/     Rust protocol structs and codec
crates/kymorem-core/         Rust layout/routing primitives
crates/kymorem-input/        Rust input abstraction
apps/kymorem-agent/          Rust CLI agent prototype
apps/android/                Android shell
install/                     Practical install scripts
packaging/                   Release packaging recipes
docs/                        Technical and operational documentation
docs/localized/              IT, EN and CH quick-start guides
screenshot.png                README screenshot
assets/themes/               Theme tokens
```

## Documentation

- [IT quick start](docs/localized/README.it.md)
- [EN quick start](docs/localized/README.en.md)
- [CH quick start](docs/localized/README.ch.md)
- [Architecture](docs/architecture.md)
- [Service Design](docs/service.md)
- [Configuration](docs/configuration.md)
- [Networking](docs/networking.md)
- [Protocol](docs/protocol.md)
- [Cryptography](docs/cryptography.md)
- [LAN Discovery](docs/discovery.md)
- [Operations](docs/operations.md)
- [Email Relay](docs/email-relay.md)
- [Localization](docs/localization.md)
- [Tray Integration](docs/tray.md)
- [Themes](docs/themes.md)
- [Debugging](DEBUGGING.md)
- [FAQ](FAQ.md)
- [Security](SECURITY.md)
- [Release Process](docs/release.md)

## Security Notice

KyMoRem controls local input. Deploy it only on networks where device access,
firewall policy and token distribution are managed. Replace the development
token before use. KyMoRem refuses the placeholder token unless
`KYMOREM_ALLOW_DEFAULT_TOKEN=1` is set for diagnostics. Do not expose
`54865/tcp` or `54866/udp` to untrusted networks. Clipboard file transfer is
bounded by `clipboard.max_file_bytes` and should be enabled only for trusted
clients.

## License

MIT.
