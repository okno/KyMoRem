# KyMoRem Avvio Rapido IT

KyMoRem condivide tastiera e puntatore in LAN. Un host controlla gli input
fisici; uno o piu client ricevono eventi cifrati e li iniettano nella sessione
grafica locale.

## Host Windows

1. Installa `KyMoRem-0.2.0-rc1-windows-x64-setup.exe`.
2. Apri `%APPDATA%\KyMoRem\config.json`.
3. Sostituisci `token` con un valore lungo, casuale e condiviso.
4. Avvia KyMoRem.
5. Seleziona `Server`, attiva `SERVER ON` e posiziona i client nella mappa.

## Client Linux X11

```bash
tar -xzf KyMoRem-0.2.0-rc1-linux-x64-standalone.tar.gz
cd KyMoRem-linux-x64-standalone
export KYMOREM_TOKEN="token-lungo-condiviso"
./run-client.sh
```

Per installazione come demone utente:

```bash
./install-daemon.sh
nano ~/.config/kymorem/kymorem.env
systemctl --user restart kymorem-client.service
```

## Client Windows diretto

```powershell
KyMoRem.exe --client --bind 0.0.0.0 --port 54865 --name windows-client
```

## Uso

Assegna ogni client a una posizione rispetto al server: `right`, `left`, `up`
o `down`. Il bordo viene attivato solo se esiste un client configurato per quel
lato. Il puntatore entra nel display di destinazione in posizione
proporzionale: uscita al 75 percento dell'altezza del server significa ingresso
al 75 percento dell'altezza del client.

Per uscire dalla modalita remota usa `Ctrl+Esc` sull'host o il bordo di ritorno
del client.

## Test

```bash
export KYMOREM_TOKEN="token-lungo-condiviso"
./run-test.sh 127.0.0.1 54865
```

## Porte

```text
54865/tcp  sessione cifrata
54866/udp  discovery LAN cifrata
```

## Sicurezza

Usa KyMoRem solo su LAN fidate. Il token di sviluppo viene rifiutato per
default. Non pubblicare `54865/tcp` o `54866/udp` su reti non controllate.
