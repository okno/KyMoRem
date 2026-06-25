# KyMoRem Linux Standalone

Pacchetto standalone per test manuali e servizio daemon utente.

## Test Manuale

```bash
export KYMOREM_TOKEN="token-lungo-condiviso"
./run-client.sh
```

In un altro terminale:

```bash
export KYMOREM_TOKEN="token-lungo-condiviso"
./run-test.sh 127.0.0.1 54865
```

## Installazione Come Demone

```bash
./install-daemon.sh
nano ~/.config/kymorem/kymorem.env
systemctl --user restart kymorem-client.service
```

Controllo stato:

```bash
systemctl --user status kymorem-client.service
```

## Disinstallazione

```bash
./uninstall-daemon.sh
```

Nota: il servizio e utente, non system-wide, perche l'iniezione input richiede
la sessione X attiva.
