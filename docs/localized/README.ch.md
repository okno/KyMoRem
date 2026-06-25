# KyMoRem Schnellstart CH

KyMoRem teilt Tastatur und Mauszeiger in einem vertrauenswuerdigen LAN. Der
Host besitzt die physischen Eingabegeraete; Clients empfangen verschluesselte
Ereignisse und injizieren sie in die lokale grafische Sitzung.

## Windows Host

1. `KyMoRem-0.2.0-rc1-windows-x64-setup.exe` installieren.
2. `%APPDATA%\KyMoRem\config.json` oeffnen.
3. `token` durch einen langen, zufaelligen gemeinsamen Wert ersetzen.
4. KyMoRem starten.
5. `Server` waehlen, `SERVER ON` aktivieren und Clients in der Karte platzieren.

## Linux X11 Client

```bash
tar -xzf KyMoRem-0.2.0-rc1-linux-x64-standalone.tar.gz
cd KyMoRem-linux-x64-standalone
export KYMOREM_TOKEN="eigenes-langes-token"
./run-client.sh
```

Als Benutzer-Daemon:

```bash
./install-daemon.sh
nano ~/.config/kymorem/kymorem.env
systemctl --user restart kymorem-client.service
```

## Direkter Windows Client

```powershell
KyMoRem.exe --client --bind 0.0.0.0 --port 54865 --name windows-client
```

## Nutzung

Jeder Client wird relativ zum Server platziert: `right`, `left`, `up` oder
`down`. Eine Bildschirmkante wird nur aktiv, wenn fuer diese Seite ein Client
konfiguriert ist. Der Mauszeiger erscheint proportional auf dem Zielbildschirm:
Verlassen bei 75 Prozent der Host-Hoehe bedeutet Eintritt bei 75 Prozent der
Client-Hoehe.

Mit `Ctrl+Esc` auf dem Host oder ueber die Rueckkehrkante des Clients wird die
Remote-Steuerung beendet.

## Client immer empfangsbereit

Wenn der KyMoRem-Client laeuft, bleibt das Zielsystem fuer Remote-Eingaben
bereit. Der Linux-X11-Client deaktiviert Session-Blanking/DPMS, fordert wenn
verfuegbar einen systemd-Inhibitor fuer Idle/Sleep an und schaltet das Display
vor Maus- oder Tastaturinjektion wieder ein. Der direkte Windows-Client nutzt
`SetThreadExecutionState`, damit System und Display waehrend des Listeners
angefordert bleiben.

KyMoRem umgeht keine Sperrbildschirme, Passwoerter, Firmware-Sleep-Zustaende
oder Wake-on-LAN-Anforderungen. Wenn ein Rechner bereits hardwareseitig
vollstaendig suspendiert ist, kann der Netzwerk-Listener nicht laufen; dafuer
muss die Wake-Policy von Betriebssystem oder Firmware separat konfiguriert
werden.

## Test

```bash
export KYMOREM_TOKEN="eigenes-langes-token"
./run-test.sh 127.0.0.1 54865
```

## Ports

```text
54865/tcp  verschluesselte Sitzung
54866/udp  verschluesselte LAN-Discovery
```

## Sicherheit

KyMoRem nur in vertrauenswuerdigen LANs verwenden. Der Entwicklungs-Token wird
standardmaessig abgelehnt. `54865/tcp` und `54866/udp` nicht ins Internet oder
in unkontrollierte Netze freigeben.
