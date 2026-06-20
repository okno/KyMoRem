#!/usr/bin/env python3
import argparse
import os
import signal
import socket
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path

from kymorem_common import APP_AUTHOR, APP_NAME, DEFAULT_TOKEN, DISCOVERY_PORT, PORT, VERSION, frame
from kymorem_crypto import CryptoError, secure_accept, validate_token
from kymorem_discovery import DiscoveryBeacon


def _runtime_dir() -> Path:
    base = os.environ.get("KYMOREM_RUNTIME_DIR") or os.environ.get("XDG_RUNTIME_DIR")
    if not base:
        uid = os.getuid() if hasattr(os, "getuid") else "user"
        base = str(Path(tempfile.gettempdir()) / f"kymorem-{uid}")
    path = Path(base)
    path.mkdir(mode=0o700, parents=True, exist_ok=True)
    try:
        path.chmod(0o700)
    except OSError:
        pass
    return path


RUNTIME_DIR = _runtime_dir()
PID_FILE = RUNTIME_DIR / "kymorem-client.pid"
LOG_FILE = RUNTIME_DIR / "kymorem-client.log"

BUTTONS = {
    "left": "1",
    "right": "3",
    "middle": "2",
}

MAX_MOVE_DELTA = 4096

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
    home = env.get("HOME", str(Path.home()))
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
        validate_token(token)
        self.bind = bind
        self.port = port
        self.name = name
        self.token = token
        self.width, self.height = screen_size()
        self.stop = threading.Event()
        self.discovery = DiscoveryBeacon(token, "client", name, port)

    def serve(self) -> None:
        self._write_pid()
        self._verify_session()
        self._verify_tools()
        self.discovery.start()
        log(f"{APP_NAME} client {VERSION} by {APP_AUTHOR} listening on {self.bind}:{self.port}")

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
            self.move_pointer(clamp_delta(payload.get("dx", 0)), clamp_delta(payload.get("dy", 0)))
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
            if shutil.which(tool) is None:
                raise RuntimeError(f"{tool} is required")

    def _verify_session(self) -> None:
        session = os.environ.get("XDG_SESSION_TYPE", "").lower()
        if session == "wayland" and os.environ.get("KYMOREM_ALLOW_WAYLAND") != "1":
            raise RuntimeError(
                "Wayland session detected. KyMoRem v0.1.1 Linux client targets X11; "
                "start an X11 session or set KYMOREM_ALLOW_WAYLAND=1 only for diagnostics."
            )

    def _write_pid(self) -> None:
        flags = os.O_WRONLY | os.O_CREAT | os.O_TRUNC
        if hasattr(os, "O_NOFOLLOW"):
            flags |= os.O_NOFOLLOW
        fd = os.open(PID_FILE, flags, 0o600)
        with os.fdopen(fd, "w", encoding="ascii") as handle:
            handle.write(str(os.getpid()))


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


def clamp_delta(value) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError):
        return 0
    return max(-MAX_MOVE_DELTA, min(MAX_MOVE_DELTA, number))


def _cmdline_for_pid(pid: str) -> str:
    try:
        return Path(f"/proc/{pid}/cmdline").read_text(encoding="utf-8", errors="ignore").replace("\x00", " ")
    except OSError:
        return ""


def free_socket(port: int, proto: str = "tcp") -> None:
    fuser = shutil.which("fuser")
    if not fuser:
        return
    result = subprocess.run([fuser, "-n", proto, str(port)], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True, check=False)
    for pid in result.stdout.split():
        cmdline = _cmdline_for_pid(pid).lower()
        if "kymorem" not in cmdline:
            log(f"port {port}/{proto} is owned by non-KyMoRem pid {pid}; refusing to kill it")
            continue
        try:
            os.kill(int(pid), signal.SIGTERM)
            log(f"stopped stale KyMoRem pid {pid} on {port}/{proto}")
        except (ProcessLookupError, PermissionError, ValueError) as exc:
            log(f"cannot stop pid {pid} on {port}/{proto}: {exc}")


def main() -> int:
    parser = argparse.ArgumentParser(description="KyMoRem Linux client")
    parser.add_argument("--bind", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=PORT)
    parser.add_argument("--name", default=socket.gethostname())
    parser.add_argument("--token", default=os.environ.get("KYMOREM_TOKEN", DEFAULT_TOKEN))
    args = parser.parse_args()

    stop_running_instance()
    free_socket(args.port, "tcp")
    free_socket(DISCOVERY_PORT, "udp")
    try:
        agent = ClientAgent(args.bind, args.port, args.name, args.token)
        agent.serve()
    except CryptoError as exc:
        log(f"security configuration error: {exc}")
        return 64
    except KeyboardInterrupt:
        return 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
