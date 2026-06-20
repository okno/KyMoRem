#!/usr/bin/env python3
import argparse
import os
import signal
import socket
import subprocess
import sys
import threading
import time
from pathlib import Path

from kymorem_common import APP_NAME, DEFAULT_TOKEN, PORT, VERSION, frame
from kymorem_crypto import CryptoError, secure_accept
from kymorem_discovery import DiscoveryBeacon


PID_FILE = Path("/tmp/kymorem-client.pid")
LOG_FILE = Path("/tmp/kymorem-client.log")

BUTTONS = {
    "left": "1",
    "right": "3",
    "middle": "2",
}

KEYS = {
    **{f"VK_{chr(code)}": chr(code).lower() for code in range(ord("A"), ord("Z") + 1)},
    **{f"VK_{n}": str(n) for n in range(0, 10)},
    "VK_RETURN": "Return",
    "VK_ESCAPE": "Escape",
    "VK_BACK": "BackSpace",
    "VK_TAB": "Tab",
    "VK_SPACE": "space",
    "VK_LEFT": "Left",
    "VK_RIGHT": "Right",
    "VK_UP": "Up",
    "VK_DOWN": "Down",
    "VK_DELETE": "Delete",
    "VK_HOME": "Home",
    "VK_END": "End",
    "VK_PRIOR": "Page_Up",
    "VK_NEXT": "Page_Down",
    "VK_LWIN": "Super_L",
    "VK_RWIN": "Super_R",
}


def log(message: str) -> None:
    line = f"{time.strftime('%Y-%m-%d %H:%M:%S')} {message}"
    print(line, flush=True)
    try:
        with LOG_FILE.open("a", encoding="utf-8") as handle:
            handle.write(line + "\n")
    except OSError:
        pass


def env_for_x() -> dict[str, str]:
    env = os.environ.copy()
    env.setdefault("DISPLAY", ":0")
    home = env.get("HOME", "/home/linux")
    xauth = Path(home) / ".Xauthority"
    if xauth.exists():
        env.setdefault("XAUTHORITY", str(xauth))
    return env


def run_xdotool(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["xdotool", *args],
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env=env_for_x(),
    )


def pointer_location() -> tuple[int, int]:
    result = run_xdotool("getmouselocation", "--shell")
    x = 0
    y = 0
    for line in result.stdout.splitlines():
        if line.startswith("X="):
            x = int(line.split("=", 1)[1])
        elif line.startswith("Y="):
            y = int(line.split("=", 1)[1])
    return x, y


def screen_size() -> tuple[int, int]:
    result = subprocess.run(
        ["xdpyinfo"],
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env=env_for_x(),
    )
    for line in result.stdout.splitlines():
        line = line.strip()
        if line.startswith("dimensions:"):
            size = line.split()[1]
            width, height = size.split("x", 1)
            return int(width), int(height)
    return 1920, 1080


class ClientAgent:
    def __init__(self, bind: str, port: int, name: str, token: str):
        self.bind = bind
        self.port = port
        self.name = name
        self.token = token
        self.width, self.height = screen_size()
        self.stop = threading.Event()
        self.discovery = DiscoveryBeacon(token, "client", name, port)

    def serve(self) -> None:
        self._write_pid()
        self._verify_tools()
        self.discovery.start()
        log(f"{APP_NAME} client {VERSION} listening on {self.bind}:{self.port}")

        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server:
                server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                server.bind((self.bind, self.port))
                server.listen(4)
                while not self.stop.is_set():
                    conn, addr = server.accept()
                    thread = threading.Thread(target=self.handle, args=(conn, addr), daemon=True)
                    thread.start()
        finally:
            self.discovery.close()

    def handle(self, conn: socket.socket, addr) -> None:
        log(f"server connected from {addr[0]}:{addr[1]}")
        with conn:
            try:
                link = secure_accept(
                    conn,
                    self.token,
                    {
                        "role": "client",
                        "name": self.name,
                        "platform": "linux",
                        "version": VERSION,
                        "port": self.port,
                    },
                )
                log(f"secure transport established with {addr[0]}:{addr[1]} using {link.suite}")
                link.send(
                    frame(
                        "hello",
                        role="client",
                        name=self.name,
                        os="linux",
                        width=self.width,
                        height=self.height,
                    )
                )
            except CryptoError as exc:
                log(f"secure handshake rejected from {addr[0]}:{addr[1]}: {exc}")
                return
            for message in link.read_frames():
                kind = message.get("type")
                payload = message.get("payload", {})
                try:
                    self.dispatch(link, kind, payload)
                except Exception as exc:
                    log(f"dispatch error for {kind}: {exc}")
                    link.send(frame("error", message=str(exc), event=kind))

    def dispatch(self, link, kind: str, payload: dict) -> None:
        if kind == "hello":
            link.send(frame("status", state="connected", name=self.name))
        elif kind == "pulse":
            self.move_pointer(36, 0)
            self.move_pointer(-36, 0)
            link.send(frame("pulse_ack", name=self.name))
        elif kind == "move":
            self.move_pointer(int(payload.get("dx", 0)), int(payload.get("dy", 0)))
            self.report_edge(link)
        elif kind == "button":
            button = BUTTONS.get(str(payload.get("button", "left")), "1")
            state = str(payload.get("state", "up"))
            run_xdotool("mousedown" if state == "down" else "mouseup", button)
        elif kind == "wheel":
            dy = int(payload.get("dy", 0))
            button = "5" if dy < 0 else "4"
            for _ in range(max(1, min(8, abs(dy) // 120 or 1))):
                run_xdotool("click", button)
        elif kind == "key":
            key = KEYS.get(str(payload.get("key", "")))
            if key:
                state = str(payload.get("state", "up"))
                run_xdotool("keydown" if state == "down" else "keyup", key)
        elif kind == "release":
            link.send(frame("released", name=self.name))

    def move_pointer(self, dx: int, dy: int) -> None:
        if dx == 0 and dy == 0:
            return
        run_xdotool("mousemove_relative", "--", str(dx), str(dy))

    def report_edge(self, link) -> None:
        x, y = pointer_location()
        if x <= 1:
            link.send(frame("edge", edge="left", x=x, y=y))
        elif x >= self.width - 2:
            link.send(frame("edge", edge="right", x=x, y=y))

    def _verify_tools(self) -> None:
        for tool in ["xdotool", "xdpyinfo"]:
            if subprocess.run(["which", tool], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode != 0:
                raise RuntimeError(f"{tool} is required")

    def _write_pid(self) -> None:
        PID_FILE.write_text(str(os.getpid()), encoding="ascii")


def stop_running_instance() -> None:
    if not PID_FILE.exists():
        return
    try:
        pid = int(PID_FILE.read_text(encoding="ascii").strip())
    except ValueError:
        return
    if pid == os.getpid():
        return
    try:
        os.kill(pid, signal.SIGTERM)
        time.sleep(0.5)
    except ProcessLookupError:
        pass
    except PermissionError:
        log(f"cannot stop previous pid {pid}")


def main() -> int:
    parser = argparse.ArgumentParser(description="KyMoRem Linux client")
    parser.add_argument("--bind", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=PORT)
    parser.add_argument("--name", default=socket.gethostname())
    parser.add_argument("--token", default=os.environ.get("KYMOREM_TOKEN", DEFAULT_TOKEN))
    args = parser.parse_args()

    stop_running_instance()
    agent = ClientAgent(args.bind, args.port, args.name, args.token)
    try:
        agent.serve()
    except KeyboardInterrupt:
        return 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
