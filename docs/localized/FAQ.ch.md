# KyMoRem FAQ CH

Diese FAQ sammelt die realen Probleme aus Entwicklung und Tests von
`0.2.0-rc2`.

## Definitiver Ablauf, wenn ein Client nicht funktioniert

1. Auf dem Server `RILASCIA` oder `Ctrl+Esc` druecken.
2. Alle alten KyMoRem-Client-Fenster auf der Zielmaschine schliessen.
3. KyMoRem auf dem Server neu starten.
4. Das Zielpaket auf dem Server neu erzeugen.
5. Paket auf der Zielmaschine installieren/starten.
6. Auf dem Server `AGGIORNA` druecken.
7. Pruefen, dass die Karte `ONLINE` ist.
8. Ueber die konfigurierte Kante eintreten.

## Windows 7 empfaengt keine Maus oder Tastatur

Haeufige Ursachen:

- altes Windows-7-Executable ist noch offen;
- falsche Architektur, zum Beispiel x64 auf Windows 7 x86;
- Firewall auf `54865/tcp` geschlossen;
- Paket ohne `kymorem-token.txt` gestartet;
- Layout gespeichert, aber nicht aktualisiert.

Empfohlene Loesung:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\New-KyMoRemWin7ClientPackage.ps1 -Arch x86 -Name windows7 -Direction down -Zip
```

Paket auf Windows 7 kopieren, `Install-Firewall-And-Start.cmd` als Administrator
starten, das schwarze Client-Fenster offen lassen und auf dem Server
`AGGIORNA` druecken.

## Sicherer Handshake wird abgelehnt

Wenn die Meldung sagt, dass `cryptography` benoetigt wird, ist der Client alt
oder unvollstaendig. Das rc2-Paket vom Server installieren.

Wenn die Ablehnung wiederholt von der Server-IP kommt, stimmen die Tokens nicht.
Token nicht manuell tippen. Paket neu erzeugen, damit `kymorem-token.txt` und
`%APPDATA%\KyMoRem\config.json` synchron bleiben.

## Server zeigt 0 Clients, aber Karten sind online

Discovery und TCP-Health sind verschiedene Signale:

- Discovery nutzt `54866/udp`;
- Steuerung und Health nutzen `54865/tcp`.

Wi-Fi-Isolation, VLANs oder Firewalls koennen UDP blockieren, waehrend TCP noch
funktioniert. `AGGIORNA` druecken und bei unzuverlaessigem Broadcast eine
manuelle IP verwenden.

## Maschinen wurden verschoben, aber Routing aendert nicht

Korrekte Reihenfolge:

1. Client auswaehlen.
2. Auf der Karte verschieben.
3. `SALVA` druecken.
4. `AGGIORNA` druecken.
5. Mit `Ctrl+Esc` freigeben.
6. Ueber die neue Kante eintreten.

Routing wird beim naechsten Kantenuebergang neu berechnet.

## Windows 7 ist von linux-iMac nicht erreichbar

rc2 auf Server und Windows-7-Client installieren. rc2 schliesst den alten
Remote-Endpunkt, bevor der neue geoeffnet wird; aeltere Builds konnten am
Linux-Client haengen bleiben.

Koordinaten muessen benachbart sein:

```text
server     x=0 y=0
linux-iMac x=1 y=0
windows7   x=2 y=0
```

In diesem Beispiel fuehrt die rechte Kante von `linux-iMac` zu `windows7`.

## Nach unten gehen, aber kein Pointer auf Windows 7

Pruefen, dass `windows7` wirklich unter dem Server liegt:

```text
server   x=0 y=0
windows7 x=0 y=1
```

Dann `SALVA`, `AGGIORNA` und erneut von der unteren Kante eintreten. Wenn die
Karte `STANDBY` ist, existiert das Layout, aber der TCP-Client ist nicht live.

## Endlos-Scroll blockiert alles

Das passierte mit hochaufloesenden Maeusen, wenn jeder Wheel-Tick in die Queue
ging. In rc2 wird Wheel-Input zusammengefasst, limitiert und beim
Freigeben/Clientwechsel geloescht. Server und Clients aktualisieren. Wenn
bereits eine Queue haengt, `Ctrl+Esc` druecken und den betroffenen Client
neu starten.

## Linux-Client ist online, bewegt aber nichts

X11 pruefen:

```bash
echo "$XDG_SESSION_TYPE"
echo "$DISPLAY"
ls -l "$HOME/.Xauthority"
command -v xdotool
xdotool getmouselocation
```

Fuer rc2 braucht die produktive Linux-Eingabeinjektion X11. Wayland ist kein
vollstaendiges Input-Injection-Ziel.

## Benutzerpasswoerter

KyMoRem nutzt fuer den normalen Betrieb keine Windows-, Linux-, SMB-, RDP- oder
SSH-Passwoerter. Vertrauen entsteht durch gemeinsamen Token, genehmigte Clients
und verschluesselten Kanal.

## Ports und Logs

```text
54865/tcp  verschluesselte Sitzung
54866/udp  verschluesselte Discovery
```

Server-Log:

```text
%APPDATA%\KyMoRem\server.log
```

Windows-7-Log:

```text
kymorem-win7-client.log
```

Linux-Log:

```text
${XDG_RUNTIME_DIR:-/tmp/kymorem-$UID}/kymorem-client.log
```
