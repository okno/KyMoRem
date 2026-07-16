# KyMoRem Linux Standalone IT

Pacchetto standalone per test manuali e servizio daemon utente X11.

## Installazione consigliata

Per deployment reale genera il pacchetto dal server:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\New-KyMoRemLinuxClientPackage.ps1 -Name linux-iMac -ClientHost 10.0.0.80 -Zip
```

Sul client Linux:

```bash
chmod +x *.sh
./Install-KyMoRem-Linux-Client.sh
systemctl --user status kymorem-client.service
```

## Test manuale

```bash
export KYMOREM_TOKEN="token-lungo-condiviso"
./run-client.sh
```

In un altro terminale:

```bash
export KYMOREM_TOKEN="token-lungo-condiviso"
./run-test.sh 127.0.0.1 54865
```

## Problemi frequenti

- Serve X11: verifica `echo "$XDG_SESSION_TYPE"`.
- Serve `xdotool`: verifica `command -v xdotool`.
- Senza X11 usa `Run-KyMoRem-TTY-Client.sh`: disegna una superficie testuale
  in console e supporta appunti testo tramite OSC52.
- Se il server non vede discovery, imposta IP manuale e controlla `54865/tcp`.
- Dopo cambio posizione sul server: `SALVA`, `AGGIORNA`, `Ctrl+Esc`.
- Se lo scroll blocca tutto, aggiorna server e client a rc2.

## Disinstallazione

```bash
./uninstall-daemon.sh
```

Nota: il servizio e' utente, non system-wide, perche l'iniezione input richiede
la sessione X attiva.
