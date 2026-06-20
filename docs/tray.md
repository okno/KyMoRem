# Tray Integration

## Windows

The Windows server uses `pystray`.

Menu actions:

- Open KyMoRem
- Connect client
- Take control
- Release
- Exit

Closing the window with `X` hides the UI to the tray. It does not terminate the
server or drop the active client connection.

Verification:

```powershell
Get-Process KyMoRem
Get-NetTCPConnection -RemotePort 54865
```

## Linux

The Linux client tray uses `yad --notification`.

Menu actions:

- Status
- Restart client
- Stop client
- Show log
- Quit

Verification:

```bash
pgrep -a yad
pgrep -a -f kymorem_client.py
```

If a desktop hides tray icons, the client can still run as a daemon.
