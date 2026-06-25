# KyMoRem Quick Start EN

KyMoRem shares keyboard and pointer input on a LAN. A host owns the physical
input devices; one or more clients receive encrypted events and inject them
into the local graphical session.

## Windows Host

1. Install `KyMoRem-0.2.0-rc1-windows-x64-setup.exe`.
2. Open `%APPDATA%\KyMoRem\config.json`.
3. Replace `token` with a long random shared value.
4. Start KyMoRem.
5. Select `Server`, enable `SERVER ON`, and place clients on the routing map.

## Linux X11 Client

```bash
tar -xzf KyMoRem-0.2.0-rc1-linux-x64-standalone.tar.gz
cd KyMoRem-linux-x64-standalone
export KYMOREM_TOKEN="long-shared-token"
./run-client.sh
```

For user-level daemon deployment:

```bash
./install-daemon.sh
nano ~/.config/kymorem/kymorem.env
systemctl --user restart kymorem-client.service
```

## Direct Windows Client

```powershell
KyMoRem.exe --client --bind 0.0.0.0 --port 54865 --name windows-client
```

## Usage

Assign each client to a position relative to the server: `right`, `left`, `up`
or `down`. An edge activates only when a client is configured for that side.
Pointer entry is proportional: leaving the host at 75 percent of screen height
enters the destination display at 75 percent of the client height.

Use `Ctrl+Esc` on the host or the client return edge to leave remote mode.

## Test

```bash
export KYMOREM_TOKEN="long-shared-token"
./run-test.sh 127.0.0.1 54865
```

## Ports

```text
54865/tcp  encrypted session
54866/udp  encrypted LAN discovery
```

## Security

Use KyMoRem only on trusted LANs. The development token is refused by default.
Do not expose `54865/tcp` or `54866/udp` to unmanaged networks.
