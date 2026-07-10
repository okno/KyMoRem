# KyMoRem Linux Standalone CH

Eigenstaendiges Paket fuer manuelle Tests und Benutzer-X11-Daemon.

## Empfohlene Installation

Fuer reale Deployments das Paket auf dem Server erzeugen:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\New-KyMoRemLinuxClientPackage.ps1 -Name linux-iMac -ClientHost 10.0.0.80 -Zip
```

Auf dem Linux-Client:

```bash
chmod +x *.sh
./Install-KyMoRem-Linux-Client.sh
systemctl --user status kymorem-client.service
```

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

## Haeufige Probleme

- X11 ist erforderlich: `echo "$XDG_SESSION_TYPE"` pruefen.
- `xdotool` ist erforderlich: `command -v xdotool` pruefen.
- Wenn Discovery fehlt, manuelle IP setzen und `54865/tcp` pruefen.
- Nach Layout-Aenderungen auf dem Server: `SALVA`, `AGGIORNA`, `Ctrl+Esc`.
- Wenn Wheel-Input alles blockiert, Server und Clients auf rc2 aktualisieren.

## Entfernen

```bash
./uninstall-daemon.sh
```

Hinweis: Der Dienst laeuft pro Benutzer, weil X11-Eingabeinjektion eine aktive
grafische Sitzung benoetigt.
