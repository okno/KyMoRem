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
tail -n 120 /tmp/kymorem-client.log
tail -n 80 /tmp/kymorem-tray.log
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
echo "$DISPLAY"
ls -l "$HOME/.Xauthority"
command -v xdotool
xdotool getmouselocation
```

### Tray does not appear on Linux

Check:

```bash
command -v yad
echo "$DBUS_SESSION_BUS_ADDRESS"
ls -l /run/user/$(id -u)/bus
```

The client can run without the tray.

### Pointer gets stuck on remote

Press `Ctrl+Esc`. If required, kill the Windows host:

```powershell
Stop-Process -Name KyMoRem -Force
```
