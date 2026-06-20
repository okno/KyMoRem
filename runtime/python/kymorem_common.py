import json
import socket
import time
from dataclasses import dataclass
from typing import Any


APP_NAME = "KyMoRem"
VERSION = "0.1.0"
PORT = 54865
DISCOVERY_PORT = 54866
PROTOCOL = 1
ENCODING = "utf-8"
DEFAULT_CLIENT_HOST = "127.0.0.1"
DEFAULT_TOKEN = "kymorem-local-default-change-me"


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
            yield json.loads(line.decode(ENCODING))


@dataclass
class ClientConfig:
    name: str = "linux-client"
    host: str = DEFAULT_CLIENT_HOST
    port: int = PORT
    position: str = "right"


DEFAULT_CONFIG = {
    "language": "it",
    "theme": "cyber_noir",
    "server_name": "Windows Host",
    "token": DEFAULT_TOKEN,
    "edge": "right",
    "security": {
        "required": True,
        "preferred_suite": "ml-kem-768+psk-hkdf-sha256+aes-256-gcm",
        "fallback_suite": "psk-hkdf-sha256+aes-256-gcm",
    },
    "discovery": {
        "enabled": True,
        "auto_connect": True,
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
    "clients": [
        {
            "name": "right-side-linux",
            "host": DEFAULT_CLIENT_HOST,
            "port": PORT,
            "position": "right",
        }
    ],
}


TEXT = {
    "it": {
        "title": "KyMoRem",
        "subtitle": "Keyboard Mouse Remote",
        "connect": "Connetti client",
        "disconnect": "Disconnetti",
        "take": "Prendi controllo",
        "release": "Rilascia",
        "test": "Test pulse",
        "status_ready": "Pronto",
        "status_connected": "Connesso",
        "status_disconnected": "Disconnesso",
        "server": "Server Windows",
        "client": "Client a destra",
        "log": "Eventi",
        "hint": "Sposta il puntatore oltre il bordo destro per entrare nel client.",
    },
    "en": {
        "title": "KyMoRem",
        "subtitle": "Keyboard Mouse Remote",
        "connect": "Connect client",
        "disconnect": "Disconnect",
        "take": "Take control",
        "release": "Release",
        "test": "Test pulse",
        "status_ready": "Ready",
        "status_connected": "Connected",
        "status_disconnected": "Disconnected",
        "server": "Windows Server",
        "client": "Right-side client",
        "log": "Events",
        "hint": "Move the pointer through the right edge to enter the client.",
    },
    "ch": {
        "title": "KyMoRem",
        "subtitle": "Tastatur- und Maus-Fernsteuerung",
        "connect": "Client verbinden",
        "disconnect": "Trennen",
        "take": "Kontrolle uebernehmen",
        "release": "Freigeben",
        "test": "Testimpuls",
        "status_ready": "Bereit",
        "status_connected": "Verbunden",
        "status_disconnected": "Getrennt",
        "server": "Windows Server",
        "client": "Client rechts",
        "log": "Ereignisse",
        "hint": "Den Zeiger ueber die rechte Kante bewegen, um den Client zu steuern.",
    },
}
