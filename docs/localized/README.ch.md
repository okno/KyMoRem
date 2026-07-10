# KyMoRem Schnellstart CH

KyMoRem teilt Tastatur, Mauszeiger, Wheel und Clipboard in einem LAN zwischen
genehmigten Maschinen. Der Server besitzt Maus und Tastatur; Clients empfangen
verschluesselte Ereignisse und injizieren sie in ihre lokale grafische Sitzung.

## rc2 Highlights

- Routing-Karte mit verschiebbaren Clients und `AGGIORNA` Refresh.
- Control Center zentriert im KyMoRem-Fenster.
- Windows-7-x86/x64-Paket mit automatischem Token, Firewall-Helfer und
  Server-Genehmigung.
- Linux-Paket mit Server-Token und Benutzer-X11-Service.
- Multi-Hop-Routing zwischen Clients, zum Beispiel server -> linux-iMac ->
  windows7.
- Schutz gegen hochaufloesende Gaming-Maus-Wheel-Fluten.
- Unbekannte Clients werden pending und deaktiviert gespeichert.

## Windows Host

1. `KyMoRem-0.2.0-rc2-windows-x64-setup.exe` installieren.
2. KyMoRem starten und `Server` waehlen.
3. `SERVER ON` aktivieren.
4. Genehmigte Clients auf der Karte platzieren.
5. `SALVA` und danach `AGGIORNA` druecken.

## Windows 7 Client

Paket auf dem Server erzeugen:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\New-KyMoRemWin7ClientPackage.ps1 -Arch x86 -Name windows7 -Direction down -Zip
```

Windows 7 rechts von einem bestehenden Client platzieren:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\New-KyMoRemWin7ClientPackage.ps1 -Arch x86 -Name windows7 -RelativeTo linux-iMac -Direction right -Zip
```

Paket auf Windows 7 kopieren, `Install-Firewall-And-Start.cmd` als
Administrator starten und das Client-Fenster offen lassen. Fuer spaetere Starts
`Start-KyMoRem-Win7-Client.cmd` nutzen.

## Linux X11 Client

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\New-KyMoRemLinuxClientPackage.ps1 -Name linux-iMac -ClientHost 10.0.0.80 -Zip
```

Auf Linux:

```bash
chmod +x *.sh
./Install-KyMoRem-Linux-Client.sh
systemctl --user status kymorem-client.service
```

## Nutzung

Jeder Client bekommt Koordinaten relativ zum Server. Eine Kante wird nur aktiv,
wenn auf dieser Seite ein Client existiert. Nach jeder Layout-Aenderung:

```text
SALVA -> AGGIORNA -> Ctrl+Esc -> ueber neue Kante eintreten
```

Mit `Ctrl+Esc` auf dem Host oder ueber die Rueckkehrkante des Clients wird der
Remote-Modus beendet.

## Haeufige Probleme

- Windows 7 bewegt nicht: Paket neu erzeugen, Firewall-Helfer als Administrator
  starten, alte Clients schliessen und `AGGIORNA` druecken.
- Handshake abgelehnt: Token falsch oder alter Client; Paket auf dem Server neu
  erzeugen.
- `0 client`, aber Karten online: UDP Discovery blockiert, TCP funktioniert;
  manuelle IP nutzen oder `AGGIORNA` druecken.
- Endlos-Scroll blockiert alles: Server und Clients auf rc2 aktualisieren,
  dann `Ctrl+Esc`.
- Linux online aber still: X11 mit `xdotool` ist erforderlich.

Vollstaendige FAQ: [FAQ CH](FAQ.ch.md).

## Ports

```text
54865/tcp  verschluesselte Sitzung
54866/udp  verschluesselte LAN-Discovery
```

KyMoRem nur in vertrauenswuerdigen LANs verwenden und Token-Dateien privat
halten.
