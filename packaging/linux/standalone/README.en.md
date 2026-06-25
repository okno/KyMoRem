# KyMoRem Linux Standalone

Standalone package for manual tests and a user-level daemon service.

## Manual Test

```bash
export KYMOREM_TOKEN="long-shared-token"
./run-client.sh
```

In another terminal:

```bash
export KYMOREM_TOKEN="long-shared-token"
./run-test.sh 127.0.0.1 54865
```

## Install As Daemon

```bash
./install-daemon.sh
nano ~/.config/kymorem/kymorem.env
systemctl --user restart kymorem-client.service
```

Check status:

```bash
systemctl --user status kymorem-client.service
```

## Power Saving

While the standalone client is running, KyMoRem keeps the target listening:
it disables X11 blanking/DPMS, uses `systemd-inhibit` when available, and forces
the display on before remote input. It does not unlock protected sessions and
does not replace Wake-on-LAN for machines already suspended at hardware level.

## Uninstall

```bash
./uninstall-daemon.sh
```

Note: the service is user-level, not system-wide, because input injection needs
the active X session.
