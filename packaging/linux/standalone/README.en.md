# KyMoRem Linux Standalone EN

Standalone package for manual tests and a user-level X11 daemon.

## Recommended install

For real deployment, generate the package from the server:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\New-KyMoRemLinuxClientPackage.ps1 -Name linux-iMac -ClientHost 10.0.0.80 -Zip
```

On the Linux client:

```bash
chmod +x *.sh
./Install-KyMoRem-Linux-Client.sh
systemctl --user status kymorem-client.service
```

## Manual test

```bash
export KYMOREM_TOKEN="long-shared-token"
./run-client.sh
```

In another terminal:

```bash
export KYMOREM_TOKEN="long-shared-token"
./run-test.sh 127.0.0.1 54865
```

## Frequent issues

- X11 is required: check `echo "$XDG_SESSION_TYPE"`.
- `xdotool` is required: check `command -v xdotool`.
- If discovery is missing, configure a manual IP and verify `54865/tcp`.
- After server layout changes: `SALVA`, `AGGIORNA`, `Ctrl+Esc`.
- If wheel input blocks everything, update server and clients to rc2.

## Uninstall

```bash
./uninstall-daemon.sh
```

Note: the service is user-level, not system-wide, because input injection needs
the active X session.
