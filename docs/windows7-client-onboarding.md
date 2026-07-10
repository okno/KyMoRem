# Windows 7 client onboarding

Questo flusso evita l'errore `refusing the development default token` e non
richiede di impostare variabili ambiente sul PC Windows 7.

## Metodo consigliato

Generare sempre il pacchetto dal server KyMoRem:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\New-KyMoRemWin7ClientPackage.ps1 -Arch x86 -Name windows7 -RelativeTo linux-iMac -Direction right -Zip
```

Il comando:

- legge `%APPDATA%\KyMoRem\config.json`;
- genera un token sicuro solo se quello del server manca o e' ancora quello di
  sviluppo;
- registra il client come approvato nel config del server;
- usa `host=pending`, cosi il server compilera' automaticamente l'IP reale al
  primo annuncio discovery valido;
- copia l'eseguibile Windows 7 compatibile;
- scrive `kymorem-token.txt` accanto all'eseguibile;
- crea `Start-KyMoRem-Win7-Client.cmd`;
- crea `Install-Firewall-And-Start.cmd`;
- opzionalmente crea uno zip pronto da copiare.

Con l'esempio sopra la disposizione diventa:

```text
server -> linux-iMac -> windows7
```

`linux-iMac` resta nella posizione attuale. `windows7` viene registrato alla sua
destra.

## Installazione sul PC Windows 7

1. Copiare sul PC Windows 7 tutta la cartella generata in
   `artifacts\win7-client-packages\windows7`, oppure lo zip se e' stato usato
   `-Zip`.
2. Estrarre lo zip se necessario.
3. Fare click destro su `Install-Firewall-And-Start.cmd`.
4. Scegliere `Esegui come amministratore`.
5. Lasciare aperta la finestra del client.

Dopo il primo avvio il server riceve il discovery, riconosce il nome approvato e
sostituisce `host=pending` con l'IP reale del client.

Per gli avvii successivi basta usare:

```text
Start-KyMoRem-Win7-Client.cmd
```

Quando si sostituisce un pacchetto gia' avviato, chiudere prima la vecchia
finestra del client KyMoRem. Poi avviare il nuovo
`Start-KyMoRem-Win7-Client.cmd`.

## Metodologia

- Il token non viene comunicato a mano: vive nel config del server e nel file
  sidecar `kymorem-token.txt` del pacchetto.
- L'approvazione avviene sul server, nel momento in cui viene generato il
  pacchetto.
- Un client discovery sconosciuto non diventa automaticamente attivo: viene
  salvato come `discovery_pending` e `enabled=false`.
- La posizione si decide in coordinate logiche. Per estendere un client gia'
  presente si usa `-RelativeTo <nome-client> -Direction <direzione>`.
- Il routing tra client usa la griglia del server. Se `linux-iMac` e'
  `x=1,y=0` e `windows7` e' `x=2,y=0`, uscire dal bordo destro di `linux-iMac`
  passa a `windows7`. Se le posizioni vengono cambiate, il routing segue le
  nuove coordinate.
- Se l'IP del Windows 7 e' gia' noto, si puo' sostituire il pending:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\New-KyMoRemWin7ClientPackage.ps1 -Arch x86 -Name windows7 -RelativeTo linux-iMac -Direction right -ClientHost 10.0.0.90
```

- Se l'IP non e' noto o e' DHCP, lasciare il default `-ClientHost pending`.

## Comandi utili

Client a destra del server:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\New-KyMoRemWin7ClientPackage.ps1 -Arch x86 -Name windows7 -Direction right
```

Client sotto `linux-iMac`:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\New-KyMoRemWin7ClientPackage.ps1 -Arch x86 -Name windows7 -RelativeTo linux-iMac -Direction down
```

Client Windows 7 a 64 bit:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\New-KyMoRemWin7ClientPackage.ps1 -Arch x64 -Name windows7-x64 -RelativeTo linux-iMac -Direction right
```

## Problemi ricorrenti e soluzione

### Il client parte ma non riceve mouse

Chiudere ogni vecchia finestra KyMoRem sul Windows 7, rilanciare il pacchetto
rc2 e premere `AGGIORNA` sul server. Se la scheda resta `STANDBY`, controllare
che `netstat -ano | find "54865"` mostri il listener.

### Handshake rifiutato in loop

Il token non coincide o il client e' vecchio. Rigenerare il pacchetto dal
server e non copiare token a mano.

### Errore `cryptography is required`

Il binario non contiene il runtime crypto corretto. Usare il pacchetto rc2
generato da `New-KyMoRemWin7ClientPackage.ps1`.

### Errore `UnicodeDecodeError` o `charmap`

Chiudere la vecchia console e reinstallare il pacchetto rc2. La procedura rc2
evita output localizzato nel percorso di avvio normale.

### Il layout cambia ma il bordo no

Sul server usare la sequenza:

```text
SALVA -> AGGIORNA -> Ctrl+Esc -> rientro dal nuovo bordo
```

### Windows 7 e' dietro linux-iMac

Le coordinate devono essere adiacenti. Esempio:

```text
server     x=0 y=0
linux-iMac x=1 y=0
windows7   x=2 y=0
```

In questa posizione il bordo destro di `linux-iMac` porta a `windows7`.
