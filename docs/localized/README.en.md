# KyMoRem Quick Start EN

KyMoRem shares keyboard, pointer, wheel and clipboard input on a LAN between
approved machines. The server owns the physical mouse and keyboard; clients
receive encrypted events and inject them into their local graphical session.

## rc2 highlights

- Route map with movable clients and `AGGIORNA` refresh.
- Control Center centered inside the KyMoRem window.
- Windows 7 x86/x64 package with automatic token, firewall helper and server
  approval.
- Linux package with the server token and user-level X11 service.
- Multi-hop routing between clients, for example server -> linux-iMac ->
  windows7.
- High-resolution gaming mouse wheel protection.
- Unknown clients stored as pending and disabled.

## Windows host

1. Install `KyMoRem-0.2.0-rc2-windows-x64-setup.exe`.
2. Start KyMoRem and choose `Server`.
3. Enable `SERVER ON`.
4. Place approved clients on the map.
5. Press `SALVA`, then `AGGIORNA`.

## Windows 7 client

Generate the package from the server:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\New-KyMoRemWin7ClientPackage.ps1 -Arch x86 -Name windows7 -Direction down -Zip
```

To place Windows 7 to the right of an existing client:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\New-KyMoRemWin7ClientPackage.ps1 -Arch x86 -Name windows7 -RelativeTo linux-iMac -Direction right -Zip
```

Copy the package to Windows 7, run `Install-Firewall-And-Start.cmd` as
Administrator and leave the client window open. Later starts can use
`Start-KyMoRem-Win7-Client.cmd`.

## Linux X11 client

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\New-KyMoRemLinuxClientPackage.ps1 -Name linux-iMac -ClientHost 10.0.0.80 -Zip
```

On Linux:

```bash
chmod +x *.sh
./Install-KyMoRem-Linux-Client.sh
systemctl --user status kymorem-client.service
```

## Usage

Assign every client to coordinates relative to the server. An edge activates
only when a client exists on that side. After every layout change use:

```text
SALVA -> AGGIORNA -> Ctrl+Esc -> enter from the new edge
```

Use `Ctrl+Esc` on the host or the client return edge to leave remote mode.

## Frequent issues

- Windows 7 does not move: regenerate the package, run the firewall helper as
  Administrator, close old clients and press `AGGIORNA`.
- Handshake rejected: token mismatch or old client; regenerate the package from
  the server.
- `0 client` but cards are online: UDP discovery is blocked, TCP still works;
  use a manual IP or press `AGGIORNA`.
- Infinite scroll blocks everything: update server and clients to rc2, then
  press `Ctrl+Esc`.
- Linux online but still: X11 with `xdotool` is required.

Full FAQ: [FAQ EN](FAQ.en.md).

## Ports

```text
54865/tcp  encrypted session
54866/udp  encrypted LAN discovery
```

Use KyMoRem only on trusted LANs and keep token files private.
