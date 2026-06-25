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

## Energiesparen

Solange der Standalone-Client laeuft, haelt KyMoRem das Ziel empfangsbereit:
X11-Blanking/DPMS wird deaktiviert, `systemd-inhibit` wird wenn verfuegbar
genutzt und das Display wird vor Remote-Eingaben eingeschaltet. Gesperrte
Sitzungen werden nicht entsperrt und Wake-on-LAN fuer bereits hardwareseitig
suspendierte Rechner wird dadurch nicht ersetzt.

## Entfernen

```bash
./uninstall-daemon.sh
```

Hinweis: Der Dienst laeuft pro Benutzer, weil X11-Eingabeinjektion eine aktive
grafische Sitzung benoetigt.
