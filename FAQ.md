# KyMoRem FAQ and Troubleshooting

This FAQ documents the real problems found during rc2 development and testing,
with the operational fix for each one.

## What is KyMoRem?

KyMoRem is a LAN keyboard and mouse sharing system. One host owns the physical
input devices; approved clients receive encrypted pointer, button, wheel,
clipboard and key frames.

## Which platforms work in v0.2.0-rc2?

Release-grade path:

- Windows x64 host with the KMR route console.
- Linux x64 X11 client with `xdotool` input injection.
- Windows 7 x86/x64 client through the generated client package.

Scaffolded targets remain for macOS and Rust native agents. Android now has an
app-local LAN client surface; system-wide Android control still requires a
later AccessibilityService or device-owner layer.

## Is KyMoRem compatible with Barrier?

No. KyMoRem uses a similar screen-edge workflow but has its own protocol,
discovery layer, security model and routing logic.

## Definitive recovery when a client does not work

Use this sequence before deeper debugging:

1. On the server, press `RILASCIA` or `Ctrl+Esc`.
2. Close every old KyMoRem client window on the target machine.
3. Restart the server KyMoRem app.
4. Regenerate the target package from the server token.
5. Install/start the target package.
6. Press `AGGIORNA` on the server.
7. Verify the card is `ONLINE`.
8. Enter from the configured edge.

## Windows 7 receives no mouse or keyboard events

Probable causes:

- old Win7 executable still running;
- wrong architecture package on Windows 7;
- missing firewall rule on `54865/tcp`;
- package started without the generated token file;
- server layout was changed but not refreshed.

Fix:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\New-KyMoRemWin7ClientPackage.ps1 -Arch x86 -Name windows7 -Direction down -Zip
```

Copy the generated folder or zip to Windows 7, then run
`Install-Firewall-And-Start.cmd` as Administrator. Leave the black client
window open. On the server press `AGGIORNA`.

Use `-Arch x64` only when the Windows 7 installation is really 64 bit.

## The Windows 7 console says secure handshake rejected

If the message mentions that cryptography is required, the client is an old or
incomplete binary. Install the rc2 generated package.

If the message appears repeatedly from the server IP, host and client tokens do
not match. Do not type the token by hand. Regenerate the package from the
server so `kymorem-token.txt` and `%APPDATA%\KyMoRem\config.json` match.

## Windows 7 shows `UnicodeDecodeError` or `charmap`

This was seen with older helper output on Italian Windows 7 consoles. The rc2
package avoids localized command output in the normal startup path. Regenerate
and reinstall the package. If an old console is still open, close it before
starting the new one.

## Server shows `0 client` but cards are online

Discovery and health are different signals:

- discovery is UDP broadcast on `54866/udp`;
- online health can be verified with TCP on `54865/tcp`.

Wi-Fi isolation, VLANs or Windows Firewall can block UDP while TCP still works.
If the card is configured and reachable, routing can still work. Press
`AGGIORNA`, verify the client card, and use a manual `host` value when broadcast
is unreliable.

## A client is online, another is standby/down

Check the target:

Windows:

```cmd
netstat -ano | find "54865"
```

Linux:

```bash
ss -ltnp | grep 54865
```

Then verify host, port and name in the server card. Duplicate names or stale
clients can make the wrong slot appear selected.

## I moved machines in the server UI but routing did not change

Required sequence:

1. Select the client card.
2. Move it with the UI controls or drag it.
3. Press `SALVA`.
4. Press `AGGIORNA`.
5. Release current control with `Ctrl+Esc`.
6. Enter again from the new edge.

The route decision is made on the next edge transition. A control session that
is already active keeps its current endpoint until release or switch.

## I cannot reach Windows 7 from linux-iMac

Install rc2 on the server and the Win7 client. The rc2 server explicitly closes
the old remote endpoint before connecting to the next client. Older builds
could keep the Linux endpoint alive and ignore the Win7 route transition.

Also verify that the grid is adjacent. Example:

```text
server    x=0 y=0
linux-iMac x=1 y=0
windows7  x=2 y=0
```

This means leaving the right edge of `linux-iMac` goes to `windows7`.

## I go down to Windows 7 but no arrow appears

Check that `windows7` is really below the server:

```text
server   x=0 y=0
windows7 x=0 y=1
```

Save, refresh and retry from the bottom edge. If the Win7 card is `down` but
`STANDBY`, the server has layout information but no live TCP client.

## The server keeps a visible cursor while I am on a client

The host pointer is used only as an edge trigger and recovery anchor. During
remote mode the useful pointer is on the client. Use `Ctrl+Esc` or the return
edge to release. If the host cursor still appears to chase motion, update to
rc2 and restart the host app so injected/stale motion filters are active.

## Infinite scroll freezes everything

This happens when old builds send every high-resolution wheel tick to the
socket and the client must drain the backlog. The current local build adds a
second network-level queue guard: movement and wheel frames are realtime state,
so slow clients receive the newest useful state instead of every old tick.

Apply the fix by updating the server first, then all clients. If a backlog was
already created, press `Ctrl+Esc` and restart the affected client.

Detailed policy: [docs/input-queue-policy.md](docs/input-queue-policy.md).

## Linux client is online but input does not move

Verify X11 input injection:

```bash
echo "$XDG_SESSION_TYPE"
echo "$DISPLAY"
ls -l "$HOME/.Xauthority"
command -v xdotool
xdotool getmouselocation
```

For rc2, production Linux input injection requires X11. Wayland is detected and
rejected unless a diagnostic override is set.

## Clipboard does not sync

On Linux install a clipboard tool:

```bash
sudo apt install xclip xsel
```

Enable `TESTO` in the server UI for text clipboard. Enable `FILE` only on
trusted clients because file transfer is intentionally bounded but still moves
data between machines.

## Passwords for Windows or Linux users are not used

KyMoRem does not log in with SMB, RDP or SSH for normal operation. Runtime
trust is based on the shared token and approved client list. Operating-system
user passwords are only useful when you manually administer a machine.

## Which ports are required?

```text
54865/tcp  encrypted control/input session
54866/udp  encrypted LAN discovery
```

Limit both ports to trusted LAN segments.

## Where are logs?

Windows host:

```text
%APPDATA%\KyMoRem\server.log
```

Windows 7 package:

```text
kymorem-win7-client.log
```

Linux:

```text
${XDG_RUNTIME_DIR:-/tmp/kymorem-$UID}/kymorem-client.log
${XDG_RUNTIME_DIR:-/tmp/kymorem-$UID}/kymorem-tray.log
```

## What should I attach to a bug report?

- KyMoRem version.
- Server `config.json` with token removed.
- Last 120 lines of server log.
- Last 120 lines of client log.
- Screenshot of the route map.
- Exact physical movement: for example `server bottom edge -> windows7`.
