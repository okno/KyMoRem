# KyMoRem Linux Standalone

Eigenstaendiges Linux-Paket fuer manuelle Tests und Benutzer-Daemon.

## Manueller Test

```bash
export KYMOREM_TOKEN="eigenes-langes-token"
./run-client.sh
```

In einem zweiten Terminal:

```bash
export KYMOREM_TOKEN="eigenes-langes-token"
./run-test.sh 127.0.0.1 54865
```

## Installation als Benutzer-Daemon

```bash
./install-daemon.sh
nano ~/.config/kymorem/kymorem.env
systemctl --user restart kymorem-client.service
```

Status:

```bash
systemctl --user status kymorem-client.service
```

## Entfernen

```bash
./uninstall-daemon.sh
```

Hinweis: Der Dienst laeuft pro Benutzer, weil X11-Eingabeinjektion eine aktive
grafische Sitzung benoetigt.
