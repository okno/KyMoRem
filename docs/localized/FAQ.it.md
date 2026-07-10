# KyMoRem FAQ IT

Questa FAQ raccoglie i problemi reali visti durante sviluppo e test della
release `0.2.0-rc2`.

## Procedura definitiva quando un client non funziona

1. Sul server premi `RILASCIA` oppure `Ctrl+Esc`.
2. Chiudi tutte le vecchie finestre client KyMoRem sulla macchina target.
3. Riavvia KyMoRem sul server.
4. Rigenera il pacchetto client dal server.
5. Installa/avvia il pacchetto sulla macchina target.
6. Premi `AGGIORNA` sul server.
7. Controlla che la scheda sia `ONLINE`.
8. Entra dal bordo configurato.

## Windows 7 non riceve mouse o tastiera

Cause piu comuni:

- eseguibile Win7 vecchio ancora aperto;
- architettura sbagliata, per esempio x64 su Windows 7 x86;
- firewall non aperto su `54865/tcp`;
- pacchetto avviato senza `kymorem-token.txt`;
- layout salvato ma non aggiornato.

Soluzione consigliata:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\New-KyMoRemWin7ClientPackage.ps1 -Arch x86 -Name windows7 -Direction down -Zip
```

Copia il pacchetto su Windows 7, esegui
`Install-Firewall-And-Start.cmd` come amministratore, lascia aperta la finestra
nera e premi `AGGIORNA` sul server.

## Handshake sicuro rifiutato

Se il messaggio dice che `cryptography` e' richiesta, stai usando un vecchio
client o un binario incompleto. Installa il pacchetto rc2 generato dal server.

Se il rifiuto arriva in loop dall'IP del server, il token non coincide. Non
scriverlo a mano: rigenera il pacchetto, cosi `kymorem-token.txt` e
`%APPDATA%\KyMoRem\config.json` restano sincronizzati.

## Il server mostra 0 client ma le schede sono online

Discovery e salute TCP sono due segnali diversi:

- discovery usa `54866/udp`;
- controllo e salute usano `54865/tcp`.

Wi-Fi isolation, VLAN o firewall possono bloccare UDP ma lasciare funzionare
TCP. Premi `AGGIORNA` e usa un IP manuale se il broadcast non e' affidabile.

## Ho spostato le macchine ma il routing non cambia

Sequenza corretta:

1. Seleziona il client.
2. Spostalo nella mappa.
3. Premi `SALVA`.
4. Premi `AGGIORNA`.
5. Rilascia con `Ctrl+Esc`.
6. Rientra dal nuovo bordo.

La decisione di routing avviene al prossimo passaggio di bordo.

## Non arrivo a Windows 7 da linux-iMac

Installa rc2 sul server e sul client Windows 7. La rc2 chiude il vecchio
endpoint remoto prima di aprire quello nuovo; build precedenti potevano restare
agganciate al client Linux.

Verifica anche che le coordinate siano adiacenti:

```text
server     x=0 y=0
linux-iMac x=1 y=0
windows7   x=2 y=0
```

In questo esempio il bordo destro di `linux-iMac` porta a `windows7`.

## Vado in basso ma su Windows 7 non appare la freccia

Controlla che `windows7` sia sotto il server:

```text
server   x=0 y=0
windows7 x=0 y=1
```

Poi `SALVA`, `AGGIORNA` e riprova dal bordo basso. Se la scheda e' `STANDBY`,
il layout esiste ma il client TCP non e' vivo.

## Lo scroll del mouse blocca tutto

Succedeva con mouse ad alta risoluzione quando ogni tick veniva inviato in
coda. In rc2 lo scroll viene compattato, limitato e pulito al rilascio/cambio
client. Aggiorna server e client. Se la coda e' gia' bloccata, premi
`Ctrl+Esc` e riavvia il client colpito.

## Il client Linux e' online ma non muove nulla

Controlla X11:

```bash
echo "$XDG_SESSION_TYPE"
echo "$DISPLAY"
ls -l "$HOME/.Xauthority"
command -v xdotool
xdotool getmouselocation
```

Per rc2 la produzione richiede X11. Wayland non e' un target completo di
iniezione input.

## Appunti e password utente

KyMoRem non usa password Windows, Linux, SMB, RDP o SSH per funzionare. Usa
token condiviso, client approvati e canale cifrato.

## Porte e log

```text
54865/tcp  sessione cifrata
54866/udp  discovery cifrata
```

Log server:

```text
%APPDATA%\KyMoRem\server.log
```

Log Windows 7:

```text
kymorem-win7-client.log
```

Log Linux:

```text
${XDG_RUNTIME_DIR:-/tmp/kymorem-$UID}/kymorem-client.log
```
