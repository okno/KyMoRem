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

## Uninstall

```bash
./uninstall-daemon.sh
```

Note: the service is user-level, not system-wide, because input injection needs
the active X session.
