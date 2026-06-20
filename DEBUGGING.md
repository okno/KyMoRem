# Debugging KyMoRem

This guide is operational and assumes access to the host and client machines.

## Windows Host

Check the process:

```powershell
Get-Process KyMoRem -ErrorAction SilentlyContinue |
  Select-Object Id,ProcessName,Path,MainWindowTitle,MainWindowHandle
```

Check the active TCP session:

```powershell
Get-NetTCPConnection -RemotePort 54865 -ErrorAction SilentlyContinue |
  Select-Object LocalAddress,LocalPort,RemoteAddress,RemotePort,State,OwningProcess
```

Check discovery socket:

```powershell
Get-NetUDPEndpoint -LocalPort 54866 -ErrorAction SilentlyContinue
```

Read logs:

```powershell
Get-Content "$env:APPDATA\KyMoRem\server.log" -Tail 120
```

Reset config:

```powershell
Remove-Item "$env:APPDATA\KyMoRem\config.json"
```

Start manually:

```powershell
& "$env:LOCALAPPDATA\KyMoRem\KyMoRem.exe"
```

## Linux Client

Check listeners:

```bash
ss -ltnp | grep 54865
ss -lunp | grep 54866
```

Check tray and client:

```bash
pgrep -a yad
pgrep -a -f kymorem_client.py
```

Read logs:

```bash
tail -n 120 "${KYMOREM_RUNTIME_DIR:-${XDG_RUNTIME_DIR:-/tmp/kymorem-$(id -u)}}/kymorem-client.log"
tail -n 80 "${KYMOREM_RUNTIME_DIR:-${XDG_RUNTIME_DIR:-/tmp/kymorem-$(id -u)}}/kymorem-tray.log"
tail -n 80 /tmp/kymorem-tray.launch.log
```

Secure pulse test:

```bash
export KYMOREM_TOKEN="same-token-as-host"
cd KyMoRem-linux-x64-standalone
./run-test.sh 127.0.0.1 54865
```

Expected response includes:

```text
'type': 'pulse_ack'
```

## Common Failure Modes

### Discovery does not find a client

Check UDP and token:

```bash
ss -lunp | grep 54866
echo "$KYMOREM_TOKEN"
```

Broadcast may be blocked by Wi-Fi isolation, VLAN policy or host firewall. Set
`clients[0].host` manually when broadcast is unavailable.

### TCP connects but secure handshake fails

Most common causes:

- host and client tokens differ;
- old client code is still running;
- crypto dependency is missing on the client.

Linux dependency check:

```bash
/opt/kymorem/venv/bin/python - <<'PY'
import cryptography
try:
    from pqcrypto.kem import ml_kem_768
    print("pqcrypto: OK")
except Exception as exc:
    print("pqcrypto: unavailable", exc)
print("cryptography:", cryptography.__version__)
PY
```

### Linux listener is up but input does not move

Check X11 access:

```bash
echo "$XDG_SESSION_TYPE"
echo "$DISPLAY"
ls -l "$HOME/.Xauthority"
command -v xdotool
xdotool getmouselocation
```

If `XDG_SESSION_TYPE` is `wayland`, KyMoRem exits with a clear diagnostic by
default. Use an X11 session for the v0.2.0-rc1 Linux client.

### Client exits immediately with a Wayland message

This is intentional. The current Linux backend uses X11 input injection. To run
diagnostic experiments only:

```bash
export KYMOREM_ALLOW_WAYLAND=1
./run-client.sh
```

Do not treat this override as production Wayland support.

### Socket Remains Busy After A Crash

The client frees the two default sockets at startup only when the owner process
is KyMoRem. Manual recovery should prefer process-name cleanup:

```bash
pkill -f kymorem_client.py || true
ss -ltnup | grep -E '54865|54866' || true
```

Avoid broad `fuser -k` cleanup unless an operator has verified the port owner.

### Tray Does Not Appear On Linux

Check:

```bash
command -v yad
echo "$DBUS_SESSION_BUS_ADDRESS"
ls -l /run/user/$(id -u)/bus
```

The client can run without the tray.

### Modifier Keys Do Not Work

The Linux client must map modifier events to X11 key names:

```text
VK_LSHIFT -> Shift_L
VK_RSHIFT -> Shift_R
VK_LCONTROL -> Control_L
VK_RCONTROL -> Control_R
VK_LMENU -> Alt_L
VK_RMENU -> Alt_R
```

If combinations still fail, verify `xdotool` and confirm the session is X11.
Wayland blocks this class of input injection.

### Clipboard Sync Does Not Work

Linux clipboard sync requires `xclip` or `xsel`:

```bash
sudo apt install xclip xsel
```

Enable TEXT in the server UI for text clipboard. Enable FILES as well for
bounded file transfer.

### Pointer gets stuck on remote

Press `Ctrl+Esc`. If required, kill the Windows host:

```powershell
Stop-Process -Name KyMoRem -Force
```

## Barrier Migration Checks

When replacing Barrier on the same machines:

```bash
pkill -f "barrier|barrierc|barriers" || true
ss -ltnp | grep -E '24800|54865' || true
ss -lunp | grep 54866 || true
```

KyMoRem does not use Barrier's `24800/tcp`, SSL certificate folder, Bonjour
compatibility layer, or Barrier screen-name config.
