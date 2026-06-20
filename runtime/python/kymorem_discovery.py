import os
import platform
import socket
import threading
import time
from typing import Callable

from kymorem_common import APP_NAME, PORT, VERSION, frame
from kymorem_crypto import DISCOVERY_INTERVAL, DISCOVERY_PORT, crypto_capabilities, decrypt_discovery, encrypt_discovery


def local_ip_hint() -> str:
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.connect(("8.8.8.8", 80))
            return sock.getsockname()[0]
    except OSError:
        return "127.0.0.1"


class DiscoveryBeacon:
    def __init__(self, token: str, role: str, name: str, tcp_port: int = PORT, interval: float = DISCOVERY_INTERVAL):
        self.token = token
        self.role = role
        self.name = name
        self.tcp_port = tcp_port
        self.interval = interval
        self.stop = threading.Event()
        self.thread: threading.Thread | None = None

    def start(self) -> None:
        if self.thread and self.thread.is_alive():
            return
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()

    def close(self) -> None:
        self.stop.set()

    def _run(self) -> None:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            while not self.stop.is_set():
                payload = frame(
                    "discovery_announce",
                    app=APP_NAME,
                    version=VERSION,
                    role=self.role,
                    name=self.name,
                    host=local_ip_hint(),
                    port=self.tcp_port,
                    platform=platform.system().lower(),
                    pid=os.getpid(),
                    capabilities=crypto_capabilities(),
                )
                try:
                    sock.sendto(encrypt_discovery(self.token, payload), ("255.255.255.255", DISCOVERY_PORT))
                except Exception:
                    pass
                self.stop.wait(self.interval)


class DiscoveryListener:
    def __init__(self, token: str, on_announce: Callable[[dict, tuple], None]):
        self.token = token
        self.on_announce = on_announce
        self.stop = threading.Event()
        self.thread: threading.Thread | None = None

    def start(self) -> None:
        if self.thread and self.thread.is_alive():
            return
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()

    def close(self) -> None:
        self.stop.set()

    def _run(self) -> None:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sock.settimeout(1.0)
            sock.bind(("", DISCOVERY_PORT))
            while not self.stop.is_set():
                try:
                    data, addr = sock.recvfrom(65535)
                    payload = decrypt_discovery(self.token, data)
                    self.on_announce(payload, addr)
                except socket.timeout:
                    continue
                except Exception:
                    continue
