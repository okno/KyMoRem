from __future__ import annotations

import argparse
import base64
import os
import shutil
import signal
import socket
import sys
import threading
import time
from pathlib import Path

from kymorem_common import DEFAULT_TOKEN, PORT, VERSION, ResolvedToken, discover_runtime_token, frame
from kymorem_crypto import CryptoError, secure_accept


WHEEL_DELTA_UNIT = 120
MAX_WHEEL_STEPS_PER_FRAME = 4
EDGE_REPORT_INTERVAL = 0.45
TTY_MIN_WIDTH = 40
TTY_MIN_HEIGHT = 10


def log(message: str) -> None:
    print(f"{time.strftime('%Y-%m-%d %H:%M:%S')} {message}", flush=True)


def clamp(value: int, low: int, high: int) -> int:
    return max(low, min(high, int(value)))


def ratio(value, fallback: float = 0.5) -> float:
    try:
        raw = float(value)
    except (TypeError, ValueError):
        raw = fallback
    return max(0.0, min(1.0, raw))


def wheel_steps(value) -> int:
    try:
        delta = int(value)
    except (TypeError, ValueError):
        return 0
    steps = abs(delta) // WHEEL_DELTA_UNIT
    return min(MAX_WHEEL_STEPS_PER_FRAME, steps)


def osc52(text: str) -> None:
    payload = base64.b64encode(text.encode("utf-8")).decode("ascii")
    sys.stdout.write(f"\033]52;c;{payload}\a")
    sys.stdout.flush()


def resolve_token(args: argparse.Namespace) -> ResolvedToken:
    if args.token_file:
        try:
            return ResolvedToken(Path(args.token_file).read_text(encoding="utf-8-sig").strip(), "token_file", args.token_file)
        except OSError as exc:
            raise CryptoError(f"cannot read token file: {exc}") from exc
    if args.token:
        return ResolvedToken(args.token, "token_arg")
    env_token = os.environ.get("KYMOREM_TOKEN")
    if env_token:
        return ResolvedToken(env_token, "env")
    discovered = discover_runtime_token()
    if discovered:
        return discovered
    return ResolvedToken(DEFAULT_TOKEN, "default")


class TtySurface:
    def __init__(self, name: str):
        self.name = name
        self.width = TTY_MIN_WIDTH
        self.height = TTY_MIN_HEIGHT
        self.x = 1
        self.y = 1
        self.remote = False
        self.last_key = ""
        self.last_button = ""
        self.wheel_total = 0
        self.clipboard_text = ""
        self.last_edge_report: dict[str, float] = {}
        self.lock = threading.Lock()
        self.resize()

    def resize(self) -> None:
        size = shutil.get_terminal_size((80, 24))
        self.width = max(TTY_MIN_WIDTH, int(size.columns))
        self.height = max(TTY_MIN_HEIGHT, int(size.lines))
        self.x = clamp(self.x, 1, self.width)
        self.y = clamp(self.y, 4, self.height)

    def screen(self) -> str:
        self.resize()
        return f"{self.width}x{self.height}"

    def enter(self, edge: str, x_ratio, y_ratio) -> tuple[int, int]:
        with self.lock:
            self.resize()
            self.x = clamp(round(ratio(x_ratio) * max(1, self.width - 1)) + 1, 1, self.width)
            self.y = clamp(round(ratio(y_ratio) * max(1, self.height - 5)) + 4, 4, self.height)
            if edge == "left":
                self.x = 1
            elif edge == "right":
                self.x = self.width
            elif edge == "up":
                self.y = 4
            elif edge == "down":
                self.y = self.height
            self.remote = True
            self.draw()
            return self.x, self.y

    def move(self, dx: int, dy: int) -> None:
        with self.lock:
            self.resize()
            self.x = clamp(self.x + int(dx), 1, self.width)
            self.y = clamp(self.y + int(dy), 4, self.height)
            self.draw()

    def wheel(self, dx: int, dy: int) -> None:
        with self.lock:
            self.wheel_total = clamp(self.wheel_total + wheel_steps(dx) + wheel_steps(dy), -9999, 9999)
            self.draw()

    def button(self, button: str, state: str) -> None:
        with self.lock:
            self.last_button = f"{button} {state}"
            self.draw()

    def key(self, key: str, state: str) -> None:
        with self.lock:
            self.last_key = f"{key} {state}"
            if state == "down" and key.startswith("VK_") and len(key) == 4:
                self.clipboard_text += key[-1].lower()
                self.clipboard_text = self.clipboard_text[-512:]
            self.draw()

    def release(self) -> None:
        with self.lock:
            self.remote = False
            self.last_button = ""
            self.last_key = ""
            self.draw()

    def edge(self) -> str:
        with self.lock:
            if self.x <= 1:
                return "left"
            if self.x >= self.width:
                return "right"
            if self.y <= 4:
                return "up"
            if self.y >= self.height:
                return "down"
            return ""

    def can_report_edge(self, edge: str) -> bool:
        now = time.monotonic()
        last = float(self.last_edge_report.get(edge, 0.0))
        if now - last < EDGE_REPORT_INTERVAL:
            return False
        self.last_edge_report[edge] = now
        return True

    def draw(self) -> None:
        sys.stdout.write("\033[?25l\033[H\033[2J")
        status = "REMOTE" if self.remote else "STANDBY"
        header = f"KyMoRem TTY {VERSION} // {self.name} // {status} // {self.screen()}"
        sys.stdout.write(header[: self.width] + "\n")
        sys.stdout.write(f"key={self.last_key} button={self.last_button} wheel={self.wheel_total}\n")
        sys.stdout.write("clipboard buffer: " + self.clipboard_text[-max(0, self.width - 18) :] + "\n")
        sys.stdout.write("-" * self.width + "\n")
        row = max(4, min(self.height, self.y))
        col = max(1, min(self.width, self.x))
        sys.stdout.write(f"\033[{row};{col}H@")
        sys.stdout.flush()

    def close(self) -> None:
        sys.stdout.write("\033[?25h\033[0m\n")
        sys.stdout.flush()


class TtyClient:
    def __init__(self, bind: str, port: int, name: str, token: str):
        self.bind = bind
        self.port = int(port)
        self.name = name
        self.token = token
        self.stop = threading.Event()
        self.surface = TtySurface(name)

    def run(self) -> None:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server:
            server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            server.bind((self.bind, self.port))
            server.listen(8)
            log(f"KyMoRem TTY client {VERSION} listening on {self.bind}:{self.port}")
            self.surface.draw()
            while not self.stop.is_set():
                try:
                    sock, addr = server.accept()
                except OSError:
                    break
                thread = threading.Thread(target=self._handle, args=(sock, addr), daemon=True)
                thread.start()

    def _handle(self, sock: socket.socket, addr) -> None:
        try:
            with sock:
                sock.settimeout(20)
                link = secure_accept(
                    sock,
                    self.token,
                    {"role": "client", "name": self.name, "platform": "linux-tty", "version": VERSION, "port": self.port},
                )
                sock.settimeout(None)
                log(f"secure session from {addr[0]}:{addr[1]} // {link.suite}")
                for message in link.read_frames():
                    self.dispatch(link, message.get("type"), message.get("payload", {}))
        except Exception as exc:
            log(f"session ended: {exc}")

    def dispatch(self, link, kind: str, payload: dict) -> None:
        if kind == "health_probe":
            link.send(frame("health_ack", name=self.name, os="linux-tty", platform="linux-tty", screen=self.surface.screen(), version=VERSION))
        elif kind == "hello":
            link.send(frame("status", state="connected", name=self.name, platform="linux-tty"))
        elif kind == "keepalive":
            link.send(frame("keepalive_ack", name=self.name, screen=self.surface.screen()))
        elif kind == "enter":
            edge = str(payload.get("edge", "left"))
            x, y = self.surface.enter(edge, payload.get("x_ratio"), payload.get("y_ratio"))
            link.send(frame("entered", name=self.name, edge=edge, x=x, y=y, screen=self.surface.screen()))
        elif kind == "move":
            self.surface.move(int(payload.get("dx", 0)), int(payload.get("dy", 0)))
            self.report_edge(link)
        elif kind == "wheel":
            self.surface.wheel(int(payload.get("dx", 0)), int(payload.get("dy", 0)))
        elif kind == "button":
            self.surface.button(str(payload.get("button", "left")), str(payload.get("state", "up")))
        elif kind == "key":
            self.surface.key(str(payload.get("key", "")), str(payload.get("state", "up")))
        elif kind == "release":
            self.surface.release()
            link.send(frame("released", name=self.name))
        elif kind == "locate_pointer":
            link.send(frame("pointer_position", name=self.name, x=self.surface.x, y=self.surface.y, screen=self.surface.screen()))
        elif kind == "clipboard_text":
            text = str(payload.get("text", ""))
            self.surface.clipboard_text = text[-512:]
            osc52(text)
            self.surface.draw()
            link.send(frame("clipboard_ack", mode="text", bytes=len(text.encode("utf-8"))))
        elif kind == "clipboard_request":
            link.send(frame("clipboard_text", text=self.surface.clipboard_text, source=self.name))

    def report_edge(self, link) -> None:
        edge = self.surface.edge()
        if edge and self.surface.can_report_edge(edge):
            link.send(
                frame(
                    "edge",
                    edge=edge,
                    x=self.surface.x,
                    y=self.surface.y,
                    left=0,
                    top=0,
                    width=self.surface.width,
                    height=self.surface.height,
                )
            )


def main() -> int:
    parser = argparse.ArgumentParser(description="KyMoRem text-mode Linux TTY client")
    parser.add_argument("--bind", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=PORT)
    parser.add_argument("--name", default=socket.gethostname() + "-tty")
    parser.add_argument("--token", default=None)
    parser.add_argument("--token-file", default=None)
    args = parser.parse_args()
    client: TtyClient | None = None
    try:
        resolved = resolve_token(args)
        client = TtyClient(args.bind, args.port, args.name, resolved.value)

        def stop(_signum=None, _frame=None):
            client.stop.set()
            client.surface.close()

        signal.signal(signal.SIGINT, stop)
        signal.signal(signal.SIGTERM, stop)
        client.run()
        return 0
    except Exception as exc:
        if client:
            client.surface.close()
        log(f"fatal: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
