# KyMoRem Avvio Rapido IT

KyMoRem condivide tastiera, puntatore, scroll e appunti in LAN tra macchine
approvate. Il server possiede mouse e tastiera fisici; i client ricevono eventi
cifrati e li iniettano nella propria sessione grafica.

## Novita rc2

- Mappa routing con client spostabili e pulsante `AGGIORNA`.
- Control Center centrato nella finestra KyMoRem.
- Pacchetto Windows 7 x86/x64 con token automatico, firewall helper e
  approvazione server.
- Pacchetto Linux con token del server e servizio utente X11.
- Routing multi-hop tra client, per esempio server -> linux-iMac -> windows7.
- Protezione contro scroll infinito dei mouse gaming.
- Client sconosciuti salvati come pending e disabilitati.

## Host Windows

1. Installa `KyMoRem-0.2.0-rc2-windows-x64-setup.exe`.
2. Avvia KyMoRem e scegli `Server`.
3. Attiva `SERVER ON`.
4. Posiziona i client approvati sulla mappa.
5. Premi `SALVA` e poi `AGGIORNA`.

## Client Windows 7

Genera il pacchetto dal server:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\New-KyMoRemWin7ClientPackage.ps1 -Arch x86 -Name windows7 -Direction down -Zip
```

Per mettere Windows 7 a destra di un client gia presente:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\New-KyMoRemWin7ClientPackage.ps1 -Arch x86 -Name windows7 -RelativeTo linux-iMac -Direction right -Zip
```

Copia il pacchetto su Windows 7, esegui
`Install-Firewall-And-Start.cmd` come amministratore e lascia aperta la finestra
client. Per avvii successivi usa `Start-KyMoRem-Win7-Client.cmd`.

## Client Linux X11

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\New-KyMoRemLinuxClientPackage.ps1 -Name linux-iMac -ClientHost 10.0.0.80 -Zip
```

Sul client Linux:

```bash
chmod +x *.sh
./Install-KyMoRem-Linux-Client.sh
systemctl --user status kymorem-client.service
```

## Uso

Assegna ogni client a coordinate relative al server. Un bordo si attiva solo se
esiste un client su quel lato. Dopo ogni cambio layout usa:

```text
SALVA -> AGGIORNA -> Ctrl+Esc -> entra dal nuovo bordo
```

Per uscire dalla modalita remota usa `Ctrl+Esc` sull'host o il bordo di ritorno
del client.

## Problemi frequenti

- Windows 7 non si muove: rigenera il pacchetto, esegui firewall helper come
  amministratore, chiudi vecchi client e premi `AGGIORNA`.
- Handshake rifiutato: token non allineato o client vecchio; rigenera il
  pacchetto dal server.
- `0 client` ma schede online: UDP discovery bloccata, TCP ancora attivo; usa
  IP manuale o premi `AGGIORNA`.
- Scroll infinito blocca tutto: aggiorna server e client a rc2, poi
  `Ctrl+Esc`.
- Linux online ma fermo: serve sessione X11 con `xdotool`.

FAQ completa: [FAQ IT](FAQ.it.md).

## Porte

```text
54865/tcp  sessione cifrata
54866/udp  discovery LAN cifrata
```

Usa KyMoRem solo su LAN fidate e non condividere i file token.
