# KyMoRem Schnellstart

KyMoRem teilt Tastatur und Zeiger in einem vertrauenswuerdigen LAN. Der Host
steuert die Eingabegeraete, der Client empfaengt sichere Eingabeframes.

## Windows Host

1. `KyMoRem-0.1.1-windows-x64-setup.exe` installieren.
2. `%APPDATA%\KyMoRem\config.json` pruefen.
3. Einen gemeinsamen `token` fuer Host und Client setzen.
4. KyMoRem starten. Discovery findet kompatible Clients automatisch.

## Linux Client

```bash
tar -xzf KyMoRem-0.1.1-linux-x64-standalone.tar.gz
cd KyMoRem-linux-x64-standalone
export KYMOREM_TOKEN="eigenes-langes-token"
./run-client.sh
```

## Test

```bash
export KYMOREM_TOKEN="eigenes-langes-token"
./run-test.sh 127.0.0.1 54865
```

## Deinstallation

Windows:

```text
artifacts\KyMoRem-0.1.1-windows-x64-uninstall.exe
```

Linux:

```bash
sudo /opt/kymorem/uninstall_linux_client.sh
```
