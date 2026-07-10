from __future__ import annotations

import json
import os
import socket
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any


APP_NAME = "KyMoRem"
VERSION = "0.2.0-rc2"
APP_SHORT_MARK = "KMR"
APP_EXTENDED_NAME = "Keyboard Mouse Remote"
APP_AUTHOR = "Pawel Zorzan Urban AKA okno"
APP_SIGNATURE = f"{APP_NAME} by {APP_AUTHOR}"
PORT = 54865
DISCOVERY_PORT = 54866
PROTOCOL = 1
ENCODING = "utf-8"
DEFAULT_CLIENT_HOST = "127.0.0.1"
DEFAULT_TOKEN = "kymorem-local-default-change-me"
MAX_FRAME_BYTES = 65536


def now_ms() -> int:
    return int(time.time() * 1000)


def frame(kind: str, **payload: Any) -> dict[str, Any]:
    return {
        "protocol": PROTOCOL,
        "type": kind,
        "ts": now_ms(),
        "payload": payload,
    }


def encode(message: dict[str, Any]) -> bytes:
    return (json.dumps(message, separators=(",", ":"), ensure_ascii=False) + "\n").encode(ENCODING)


def send(sock: socket.socket, message: dict[str, Any]) -> None:
    sock.sendall(encode(message))


def read_frames(sock: socket.socket):
    buffer = b""
    while True:
        chunk = sock.recv(65536)
        if not chunk:
            return
        buffer += chunk
        while b"\n" in buffer:
            line, buffer = buffer.split(b"\n", 1)
            if not line.strip():
                continue
            if len(line) > MAX_FRAME_BYTES:
                raise ValueError("KyMoRem frame line exceeds maximum size")
            yield json.loads(line.decode(ENCODING))
        if len(buffer) > MAX_FRAME_BYTES:
            raise ValueError("KyMoRem pending frame exceeds maximum size")


@dataclass
class ClientConfig:
    name: str = "linux-client"
    host: str = DEFAULT_CLIENT_HOST
    port: int = PORT
    position: str = "right"


@dataclass(frozen=True)
class ResolvedToken:
    value: str
    source: str
    path: str = ""


def runtime_config_dir(env: dict[str, str] | None = None, home: Path | None = None) -> Path:
    values = os.environ if env is None else env
    if values.get("APPDATA"):
        return Path(values["APPDATA"]) / APP_NAME
    if values.get("XDG_CONFIG_HOME"):
        return Path(values["XDG_CONFIG_HOME"]) / APP_NAME
    base = Path.home() if home is None else home
    if os.name == "posix":
        return base / ".config" / APP_NAME
    return base / APP_NAME


def runtime_entry_dir(argv0: str | None = None) -> Path:
    raw = sys.executable if getattr(sys, "frozen", False) else (argv0 or sys.argv[0] or "")
    if not raw:
        return Path.cwd()
    entry = Path(raw)
    return entry if entry.is_dir() else entry.resolve().parent


def _dedupe_dirs(paths: list[Path]) -> list[Path]:
    seen: set[Path] = set()
    ordered: list[Path] = []
    for item in paths:
        try:
            candidate = item.resolve()
        except OSError:
            candidate = item
        if candidate in seen:
            continue
        seen.add(candidate)
        ordered.append(candidate)
    return ordered


def _read_text_token(path: Path) -> str | None:
    try:
        token = path.read_text(encoding="utf-8-sig").strip()
    except OSError:
        return None
    return token or None


def _read_config_token(path: Path) -> str | None:
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError):
        return None
    token = str(payload.get("token", "")).strip()
    return token or None


def discover_runtime_token(
    argv0: str | None = None,
    cwd: Path | None = None,
    env: dict[str, str] | None = None,
    home: Path | None = None,
) -> ResolvedToken | None:
    values = os.environ if env is None else env
    working_dir = Path.cwd() if cwd is None else cwd
    sidecar_dirs = _dedupe_dirs([runtime_entry_dir(argv0), working_dir])
    config_dir = runtime_config_dir(values, home)

    for directory in sidecar_dirs:
        for filename in ("kymorem-token.txt", "token.txt"):
            candidate = directory / filename
            token = _read_text_token(candidate)
            if token:
                return ResolvedToken(token, "sidecar_token", str(candidate))
        for filename in ("kymorem-config.json", "config.json"):
            candidate = directory / filename
            token = _read_config_token(candidate)
            if token:
                return ResolvedToken(token, "sidecar_config", str(candidate))

    for filename in ("kymorem-token.txt", "config.json"):
        candidate = config_dir / filename
        token = _read_text_token(candidate) if filename.endswith(".txt") else _read_config_token(candidate)
        if token:
            return ResolvedToken(token, "app_config", str(candidate))
    return None


DEFAULT_CONFIG = {
    "language": "it",
    "theme": "old_school_x11",
    "mode": "client",
    "server_on": False,
    "server_name": "Windows Host",
    "token": DEFAULT_TOKEN,
    "edge": "right",
    "layout": {
        "grid_span": 5,
        "activation_edges": True,
    },
    "security": {
        "required": True,
        "preferred_suite": "ml-kem-768+psk-hkdf-sha256+aes-256-gcm",
        "fallback_suite": "psk-hkdf-sha256+aes-256-gcm",
    },
    "clipboard": {
        "enabled": False,
        "max_bytes": 1048576,
        "text_only": True,
        "files_enabled": False,
        "max_file_bytes": 5242880,
        "chunk_bytes": 32768,
        "inbox_dir": "KyMoRem Inbox",
    },
    "discovery": {
        "enabled": True,
        "auto_connect": True,
        "auto_approve": False,
        "udp_port": DISCOVERY_PORT,
    },
    "email_relay": {
        "enabled": False,
        "smtp_host": "",
        "smtp_port": 587,
        "smtp_starttls": True,
        "smtp_username": "",
        "smtp_password_env": "KYMOREM_SMTP_PASSWORD",
        "from": "kymorem@example.invalid",
        "to": [],
        "events": ["client_connected", "client_disconnected", "security_error"],
    },
    "ui": {
        "opacity": 0.9,
    },
    "clients": [
        {
            "name": "right-side-linux",
            "host": DEFAULT_CLIENT_HOST,
            "port": PORT,
            "position": "right",
            "x": 1,
            "y": 0,
            "enabled": True,
            "source": "manual",
        }
    ],
}


TEXT = {
    "it": {
        "title": "KyMoRem",
        "subtitle": APP_EXTENDED_NAME,
        "connect": "Connetti client",
        "disconnect": "Disconnetti",
        "take": "Prendi controllo",
        "release": "Rilascia",
        "test": "Test pulse",
        "server_on": "Server ON",
        "server_off": "Server OFF",
        "client_mode": "Modo client",
        "boot_ready": "Avvio // pronto",
        "remote": "Remoto",
        "status_ready": "Pronto",
        "status_connected": "Connesso",
        "status_disconnected": "Disconnesso",
        "server": "Server Windows",
        "client": "Client a destra",
        "log": "Eventi",
        "hint": "Sposta il puntatore oltre il bordo destro per entrare nel client.",
        "node_status": "Stato nodo",
        "client_map": "Mappa client",
        "routing_map": "Mappa routing KMR",
        "client_layout": "Layout client",
        "name": "Nome",
        "ip": "IP",
        "port": "Porta",
        "position": "Pos",
        "add": "Aggiungi",
        "save": "Salva",
        "delete": "Elimina",
        "use": "Usa",
        "refresh": "Aggiorna",
        "clean": "Pulisci offline",
        "up": "Su",
        "left": "Sinistra",
        "right": "Destra",
        "down": "Giu",
        "clipboard": "Appunti",
        "text": "Testo",
        "files": "File",
        "send_text": "Invia testo",
        "get_text": "Ricevi testo",
        "send_files": "Invia file",
        "event_stream": "Eventi",
        "advanced": "Avanzate",
        "transparency": "Trasparenza",
        "opacity_saved": "Trasparenza UI salvata: {value}%.",
        "footer": "CONTROL VECTOR: SOLO BORDI CONFIGURATI // RILASCIO: Ctrl+Esc // TROVA PUNTATORE: Ctrl+Shift+M",
        "discovery_off": "Discovery // OFF",
        "discovery_armed": "Discovery // attiva",
        "discovery_disabled": "Discovery // disattivata",
        "discovery_token_required": "Discovery // token richiesto",
        "token_required": "Token richiesto",
        "client_mode_route": "Modo client // server off",
        "link_online_route": "Link online // routing bordo armato",
        "link_offline_route": "Link offline // seleziona o scopri nodo",
        "remote_route": "Controllo remoto attivo // ritorno dal bordo sinistro",
        "active": "Attivo",
        "connected_node": "Connesso",
        "online": "Online",
        "offline": "Offline",
        "standby": "Standby",
        "selected": "selezionato",
        "open_app": "Apri KyMoRem",
        "exit": "Esci",
        "language_set": "Lingua aggiornata: {label}.",
    },
    "en": {
        "title": "KyMoRem",
        "subtitle": APP_EXTENDED_NAME,
        "connect": "Connect client",
        "disconnect": "Disconnect",
        "take": "Take control",
        "release": "Release",
        "test": "Test pulse",
        "server_on": "Server ON",
        "server_off": "Server OFF",
        "client_mode": "Client mode",
        "boot_ready": "Boot // ready",
        "remote": "Remote",
        "status_ready": "Ready",
        "status_connected": "Connected",
        "status_disconnected": "Disconnected",
        "server": "Windows Server",
        "client": "Right-side client",
        "log": "Events",
        "hint": "Move the pointer through the right edge to enter the client.",
        "node_status": "Node status",
        "client_map": "Client map",
        "routing_map": "KMR routing map",
        "client_layout": "Client layout",
        "name": "Name",
        "ip": "IP",
        "port": "Port",
        "position": "Pos",
        "add": "Add",
        "save": "Save",
        "delete": "Delete",
        "use": "Use",
        "refresh": "Refresh",
        "clean": "Clean offline",
        "up": "Up",
        "left": "Left",
        "right": "Right",
        "down": "Down",
        "clipboard": "Clipboard",
        "text": "Text",
        "files": "Files",
        "send_text": "Send text",
        "get_text": "Get text",
        "send_files": "Send files",
        "event_stream": "Event stream",
        "advanced": "Advanced",
        "transparency": "Transparency",
        "opacity_saved": "UI transparency saved: {value}%.",
        "footer": "CONTROL VECTOR: CONFIGURED EDGES ONLY // RELEASE: Ctrl+Esc // FIND POINTER: Ctrl+Shift+M",
        "discovery_off": "Discovery // OFF",
        "discovery_armed": "Discovery // armed",
        "discovery_disabled": "Discovery // disabled",
        "discovery_token_required": "Discovery // token required",
        "token_required": "Token required",
        "client_mode_route": "Client mode // server off",
        "link_online_route": "Link online // edge routing armed",
        "link_offline_route": "Link offline // select or discover node",
        "remote_route": "Remote control active // return via left edge",
        "active": "Active",
        "connected_node": "Connected",
        "online": "Online",
        "offline": "Offline",
        "standby": "Standby",
        "selected": "selected",
        "open_app": "Open KyMoRem",
        "exit": "Exit",
        "language_set": "Language updated: {label}.",
    },
    "ch": {
        "title": "KyMoRem",
        "subtitle": "Tastatur- und Maus-Fernsteuerung",
        "connect": "Client verbinden",
        "disconnect": "Trennen",
        "take": "Kontrolle uebernehmen",
        "release": "Freigeben",
        "test": "Testimpuls",
        "server_on": "Server EIN",
        "server_off": "Server AUS",
        "client_mode": "Client-Modus",
        "boot_ready": "Start // bereit",
        "remote": "Fernsteuerung",
        "status_ready": "Bereit",
        "status_connected": "Verbunden",
        "status_disconnected": "Getrennt",
        "server": "Windows Server",
        "client": "Client rechts",
        "log": "Ereignisse",
        "hint": "Den Zeiger ueber die rechte Kante bewegen, um den Client zu steuern.",
        "node_status": "Knotenstatus",
        "client_map": "Client-Karte",
        "routing_map": "KMR Routing-Karte",
        "client_layout": "Client-Layout",
        "name": "Name",
        "ip": "IP",
        "port": "Port",
        "position": "Pos",
        "add": "Hinzufuegen",
        "save": "Speichern",
        "delete": "Loeschen",
        "use": "Verwenden",
        "refresh": "Aktualisieren",
        "clean": "Offline bereinigen",
        "up": "Oben",
        "left": "Links",
        "right": "Rechts",
        "down": "Unten",
        "clipboard": "Zwischenablage",
        "text": "Text",
        "files": "Dateien",
        "send_text": "Text senden",
        "get_text": "Text holen",
        "send_files": "Dateien senden",
        "event_stream": "Ereignisse",
        "advanced": "Erweitert",
        "transparency": "Transparenz",
        "opacity_saved": "UI-Transparenz gespeichert: {value}%.",
        "footer": "CONTROL VECTOR: NUR KONFIGURIERTE KANTEN // FREIGABE: Ctrl+Esc // ZEIGER FINDEN: Ctrl+Shift+M",
        "discovery_off": "Discovery // AUS",
        "discovery_armed": "Discovery // aktiv",
        "discovery_disabled": "Discovery // deaktiviert",
        "discovery_token_required": "Discovery // Token erforderlich",
        "token_required": "Token erforderlich",
        "client_mode_route": "Client-Modus // Server aus",
        "link_online_route": "Link online // Kantenrouting aktiv",
        "link_offline_route": "Link offline // Knoten waehlen oder suchen",
        "remote_route": "Fernsteuerung aktiv // Rueckkehr ueber linke Kante",
        "active": "Aktiv",
        "connected_node": "Verbunden",
        "online": "Online",
        "offline": "Offline",
        "standby": "Standby",
        "selected": "gewaehlt",
        "open_app": "KyMoRem oeffnen",
        "exit": "Beenden",
        "language_set": "Sprache aktualisiert: {label}.",
    },
}
