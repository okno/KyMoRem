# KyMoRem Avvio Rapido

KyMoRem condivide tastiera e puntatore in LAN tramite un host Windows e un
client Linux X11.

## Host Windows

1. Installa `KyMoRem-0.1.0-windows-x64-setup.exe`.
2. Apri `%APPDATA%\KyMoRem\config.json`.
3. Sostituisci `token` con un valore lungo e condiviso.
4. Avvia KyMoRem. La discovery puo trovare automaticamente il primo client.

## Client Linux

```bash
tar -xzf KyMoRem-0.1.0-linux-x64-standalone.tar.gz
cd KyMoRem-linux-x64-standalone
export KYMOREM_TOKEN="token-lungo-condiviso"
./run-client.sh
```

## Test

```bash
export KYMOREM_TOKEN="token-lungo-condiviso"
./run-test.sh 127.0.0.1 54865
```

## Uso

Quando il client e connesso, sposta il puntatore oltre il bordo destro dello
schermo host. Per uscire dalla modalita remota usa il bordo sinistro del client
oppure `Ctrl+Esc` sull'host.

## Porte

```text
54865/tcp  sessione cifrata
54866/udp  discovery LAN cifrata
```

## Disinstallazione

Windows:

```text
artifacts\KyMoRem-0.1.0-windows-x64-uninstall.exe
```

Linux:

```bash
sudo /opt/kymorem/uninstall_linux_client.sh
```
