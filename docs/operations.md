# Operations

This document is intended for administrators and operators responsible for a
KyMoRem deployment.

## Baseline Deployment

1. Install the Windows host package.
2. Install the Linux client package or standalone daemon.
3. Generate a long shared token.
4. Set the token on both endpoints.
5. Restrict `54865/tcp` and `54866/udp` to the trusted subnet.
6. Verify discovery, connection, pulse test and emergency release.

## Health Checks

Windows:

```powershell
Get-Process KyMoRem -ErrorAction SilentlyContinue
Get-NetTCPConnection -RemotePort 54865 -ErrorAction SilentlyContinue
Get-Content "$env:APPDATA\KyMoRem\server.log" -Tail 80
```

Linux:

```bash
pgrep -a -f kymorem_client.py
ss -ltnp | grep 54865
ss -lunp | grep 54866
tail -n 80 /tmp/kymorem-client.log
```

## Restart

Linux installed client:

```bash
pkill -f /opt/kymorem/kymorem_client.py || true
fuser -k 54865/tcp 54866/udp || true
DISPLAY=:0 XAUTHORITY="$HOME/.Xauthority" /opt/kymorem/start-client.sh &
```

Windows host:

```powershell
Stop-Process -Name KyMoRem -ErrorAction SilentlyContinue
& "$env:LOCALAPPDATA\KyMoRem\KyMoRem.exe"
```

## Token Rotation

1. Stop host and client.
2. Update Windows `config.json`.
3. Update Linux `KYMOREM_TOKEN`.
4. Restart client first, then host.
5. Confirm the selected suite in logs.

## Change Management

Recommended release checks:

- package checksum verification;
- smoke test with `run-test.sh`;
- tray visibility check on Windows and Linux;
- edge entry and `Ctrl+Esc` release test;
- firewall scope review.
