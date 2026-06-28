#!/usr/bin/env python3
from __future__ import annotations

import argparse
import base64
import os
import re
import signal
import socket
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import uuid
from pathlib import Path
from urllib.parse import unquote, urlparse

from kymorem_common import APP_AUTHOR, APP_NAME, DEFAULT_TOKEN, DISCOVERY_PORT, PORT, VERSION, ResolvedToken, discover_runtime_token, frame
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
MAX_ACTIVE_SESSIONS = 4
MAX_FRAMES_PER_SECOND = 1200
MAX_CLIPBOARD_BYTES = 1024 * 1024
MAX_FILE_BYTES = 5 * 1024 * 1024
WHEEL_DELTA_UNIT = 120
MAX_WHEEL_STEPS_PER_FRAME = 12
EDGE_REPORT_INTERVAL = 0.18
DISPLAY_AWAKE_INTERVAL = 20.0

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
    "VK_INSERT": "Insert",
    "VK_CAPITAL": "Caps_Lock",
    "VK_HOME": "Home",
    "VK_END": "End",
    "VK_PRIOR": "Page_Up",
    "VK_NEXT": "Page_Down",
    "VK_LWIN": "Super_L",
    "VK_RWIN": "Super_R",
    "VK_LSHIFT": "Shift_L",
    "VK_RSHIFT": "Shift_R",
    "VK_LCONTROL": "Control_L",
    "VK_RCONTROL": "Control_R",
    "VK_LMENU": "Alt_L",
    "VK_RMENU": "Alt_R",
    **{f"VK_F{n}": f"F{n}" for n in range(1, 25)},
    **{f"VK_NUMPAD{n}": f"KP_{n}" for n in range(10)},
    "VK_MULTIPLY": "KP_Multiply",
    "VK_ADD": "KP_Add",
    "VK_SEPARATOR": "KP_Separator",
    "VK_SUBTRACT": "KP_Subtract",
    "VK_DECIMAL": "KP_Decimal",
    "VK_DIVIDE": "KP_Divide",
    "VK_OEM_1": "semicolon",
    "VK_OEM_PLUS": "equal",
    "VK_OEM_COMMA": "comma",
    "VK_OEM_MINUS": "minus",
    "VK_OEM_PERIOD": "period",
    "VK_OEM_2": "slash",
    "VK_OEM_3": "grave",
    "VK_OEM_4": "bracketleft",
    "VK_OEM_5": "backslash",
    "VK_OEM_6": "bracketright",
    "VK_OEM_7": "apostrophe",
}

SAFE_FILENAME = re.compile(r"[^A-Za-z0-9._ -]+")
FALLBACK_RELEASE_KEYS = {
    "Shift_L",
    "Shift_R",
    "Control_L",
    "Control_R",
    "Alt_L",
    "Alt_R",
    "Super_L",
    "Super_R",
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


def run_optional_tool(*args: str) -> subprocess.CompletedProcess | None:
    if shutil.which(args[0]) is None:
        return None
    return subprocess.run(
        list(args),
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env=env_for_x(),
    )


def clipboard_tool() -> str | None:
    if shutil.which("xclip"):
        return "xclip"
    if shutil.which("xsel"):
        return "xsel"
    return None


def get_clipboard_text() -> str:
    tool = clipboard_tool()
    if tool == "xclip":
        result = subprocess.run(["xclip", "-selection", "clipboard", "-o"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env_for_x(), check=False)
    elif tool == "xsel":
        result = subprocess.run(["xsel", "--clipboard", "--output"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env_for_x(), check=False)
    else:
        raise RuntimeError("xclip or xsel is required for clipboard sync")
    return result.stdout[:MAX_CLIPBOARD_BYTES].decode("utf-8", errors="replace")


def set_clipboard_text(text: str) -> None:
    data = text.encode("utf-8")[:MAX_CLIPBOARD_BYTES]
    tool = clipboard_tool()
    if tool == "xclip":
        subprocess.run(["xclip", "-selection", "clipboard"], input=data, env=env_for_x(), check=False)
    elif tool == "xsel":
        subprocess.run(["xsel", "--clipboard", "--input"], input=data, env=env_for_x(), check=False)
    else:
        raise RuntimeError("xclip or xsel is required for clipboard sync")


def set_clipboard_files(paths: list[Path]) -> None:
    uris = "".join(f"file://{path.resolve().as_posix()}\n" for path in paths)
    tool = clipboard_tool()
    if tool == "xclip":
        subprocess.run(["xclip", "-selection", "clipboard", "-t", "text/uri-list"], input=uris.encode("utf-8"), env=env_for_x(), check=False)
    else:
        set_clipboard_text("\n".join(str(path) for path in paths))


def get_clipboard_file_paths() -> list[Path]:
    if not shutil.which("xclip"):
        return []
    result = subprocess.run(
        ["xclip", "-selection", "clipboard", "-t", "text/uri-list", "-o"],
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        env=env_for_x(),
        check=False,
    )
    paths: list[Path] = []
    for line in result.stdout.decode("utf-8", errors="ignore").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parsed = urlparse(line)
        if parsed.scheme != "file":
            continue
        path = Path(unquote(parsed.path))
        if path.is_file():
            paths.append(path)
    return paths


def safe_filename(name: str) -> str:
    cleaned = SAFE_FILENAME.sub("_", Path(name).name).strip(" .")
    return cleaned[:160] or "kymorem-file"


def pointer_location() -> tuple[int, int]:
    result = run_xdotool("getmouselocation", "--shell")
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "xdotool getmouselocation failed")
    x = 0
    y = 0
    for line in result.stdout.splitlines():
        if line.startswith("X="):
            x = int(line.split("=", 1)[1])
        elif line.startswith("Y="):
            y = int(line.split("=", 1)[1])
    return x, y


def pointer_window() -> str | None:
    result = run_xdotool("getmouselocation", "--shell")
    if result.returncode != 0:
        return None
    for line in result.stdout.splitlines():
        if line.startswith("WINDOW="):
            window = line.split("=", 1)[1].strip()
            if window and window != "0":
                return window
    return None


def focus_window_under_pointer() -> None:
    window = pointer_window()
    if not window:
        return
    run_xdotool("windowactivate", "--sync", window)


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


def ratio(value, fallback: float = 0.5) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return fallback
    return max(0.0, min(1.0, number))


def clamp_axis(value: int, maximum: int, margin: int = 8) -> int:
    maximum = max(0, maximum)
    lower = min(margin, maximum)
    upper = max(lower, maximum - margin)
    return max(lower, min(upper, value))


def reset_cursor_shape() -> None:
    if shutil.which("xsetroot"):
        subprocess.run(
            ["xsetroot", "-cursor_name", "left_ptr"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            env=env_for_x(),
            check=False,
        )


def release_inputs(keys: set[str], buttons: set[str]) -> None:
    for button in sorted(buttons | set(BUTTONS.values())):
        run_xdotool("mouseup", button)
    for key in sorted(keys | FALLBACK_RELEASE_KEYS):
        run_xdotool("keyup", key)


def keep_display_awake() -> bool:
    ok = False
    xset = run_optional_tool("xset", "s", "reset")
    if xset is not None and xset.returncode == 0:
        ok = True
    screensaver = run_optional_tool("xdg-screensaver", "reset")
    if screensaver is not None and screensaver.returncode == 0:
        ok = True
    return ok


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
        self.session_slots = threading.BoundedSemaphore(MAX_ACTIVE_SESSIONS)
        self.file_transfers: dict[str, dict] = {}
        self.active_keys: set[str] = set()
        self.active_buttons: set[str] = set()
        self.pointer_x = self.width // 2
        self.pointer_y = self.height // 2
        self.remote_session_active = False
        self.last_edge_report: dict[str, float] = {}
        self.last_awake_poke = 0.0
        self.last_awake_warning = 0.0
        self.awake_thread = threading.Thread(target=self._keep_awake_loop, daemon=True)
        self.awake_thread.start()

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
                    if not self.session_slots.acquire(blocking=False):
                        log(f"rejecting {addr[0]}:{addr[1]}: too many active sessions")
                        conn.close()
                        continue
                    thread = threading.Thread(target=self.handle, args=(conn, addr), daemon=True)
                    thread.start()
        finally:
            self.discovery.close()

    def handle(self, conn: socket.socket, addr) -> None:
        log(f"server connected from {addr[0]}:{addr[1]}")
        try:
            with conn:
                try:
                    conn.settimeout(12)
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
                    conn.settimeout(None)
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
                window_start = time.monotonic()
                frame_count = 0
                try:
                    for message in link.read_frames():
                        now = time.monotonic()
                        if now - window_start >= 1.0:
                            window_start = now
                            frame_count = 0
                        frame_count += 1
                        if frame_count > MAX_FRAMES_PER_SECOND:
                            log(f"rate limit exceeded by {addr[0]}:{addr[1]}")
                            link.send(frame("error", message="rate limit exceeded", event="rate_limit"))
                            break
                        kind = message.get("type")
                        payload = message.get("payload", {})
                        try:
                            self.dispatch(link, kind, payload)
                        except Exception as exc:
                            log(f"dispatch error for {kind}: {exc}")
                            link.send(frame("error", message=str(exc), event=kind))
                except (ConnectionResetError, OSError, ValueError) as exc:
                    log(f"server connection closed from {addr[0]}:{addr[1]}: {exc}")
        finally:
            self._set_remote_session_active(False)
            release_inputs(self.active_keys, self.active_buttons)
            self.active_keys.clear()
            self.active_buttons.clear()
            self.session_slots.release()

    def _set_remote_session_active(self, active: bool) -> None:
        self.remote_session_active = bool(active)
        if active:
            self.last_edge_report.clear()
            self._poke_display_awake(force=True)

    def _poke_display_awake(self, force: bool = False) -> None:
        now = time.monotonic()
        if not force and now - self.last_awake_poke < DISPLAY_AWAKE_INTERVAL:
            return
        self.last_awake_poke = now
        if keep_display_awake():
            return
        if now - self.last_awake_warning >= 60.0:
            self.last_awake_warning = now
            log("cannot refresh X11 idle timer; display blanking may resume")

    def _keep_awake_loop(self) -> None:
        while not self.stop.is_set():
            if self.remote_session_active:
                self._poke_display_awake()
            time.sleep(5.0)

    def dispatch(self, link, kind: str, payload: dict) -> None:
        if kind == "hello":
            link.send(frame("status", state="connected", name=self.name))
        elif kind == "pulse":
            self.move_pointer(36, 0)
            self.move_pointer(-36, 0)
            link.send(frame("pulse_ack", name=self.name))
        elif kind == "keepalive":
            self._set_remote_session_active(True)
            self._poke_display_awake(force=True)
            link.send(frame("keepalive_ack", name=self.name, screen=f"{self.width}x{self.height}"))
        elif kind == "locate_pointer":
            x, y = pointer_location()
            link.send(frame("pointer_position", name=self.name, x=x, y=y, screen=f"{self.width}x{self.height}"))
        elif kind == "enter":
            self._set_remote_session_active(True)
            edge = str(payload.get("edge", "left"))
            x, y = self.enter_from_edge(edge, payload.get("x_ratio"), payload.get("y_ratio"))
            link.send(frame("entered", name=self.name, edge=edge, x=x, y=y, screen=f"{self.width}x{self.height}"))
        elif kind == "move":
            self._poke_display_awake()
            self.move_pointer(clamp_delta(payload.get("dx", 0)), clamp_delta(payload.get("dy", 0)))
            self.report_edge(link)
        elif kind == "button":
            self._poke_display_awake()
            button = BUTTONS.get(str(payload.get("button", "left")), "1")
            state = str(payload.get("state", "up"))
            if state == "down":
                self.active_buttons.add(button)
            else:
                self.active_buttons.discard(button)
            run_xdotool("mousedown" if state == "down" else "mouseup", button)
        elif kind == "wheel":
            self._poke_display_awake()
            dx = int(payload.get("dx", 0))
            dy = int(payload.get("dy", 0))
            y_steps = wheel_steps(dy)
            if y_steps:
                run_xdotool("click", "--repeat", str(y_steps), "5" if dy < 0 else "4")
            x_steps = wheel_steps(dx)
            if x_steps:
                run_xdotool("click", "--repeat", str(x_steps), "7" if dx > 0 else "6")
        elif kind == "key":
            self._poke_display_awake()
            key = KEYS.get(str(payload.get("key", "")))
            if key:
                state = str(payload.get("state", "up"))
                if state == "down":
                    self.active_keys.add(key)
                else:
                    self.active_keys.discard(key)
                run_xdotool("keydown" if state == "down" else "keyup", key)
        elif kind == "release":
            self._set_remote_session_active(False)
            release_inputs(self.active_keys, self.active_buttons)
            self.active_keys.clear()
            self.active_buttons.clear()
            reset_cursor_shape()
            link.send(frame("released", name=self.name))
        elif kind == "clipboard_text":
            text = str(payload.get("text", ""))
            if len(text.encode("utf-8")) > MAX_CLIPBOARD_BYTES:
                raise RuntimeError("clipboard text exceeds client limit")
            set_clipboard_text(text)
            link.send(frame("clipboard_ack", mode="text", bytes=len(text.encode("utf-8"))))
        elif kind == "clipboard_request":
            text = get_clipboard_text()
            link.send(frame("clipboard_text", text=text, source=self.name))
            if payload.get("files"):
                for path in get_clipboard_file_paths():
                    self.send_file(link, path)
        elif kind == "file_begin":
            transfer_id = str(payload.get("transfer_id", ""))
            size = int(payload.get("size", 0))
            if not transfer_id or size < 0 or size > MAX_FILE_BYTES:
                raise RuntimeError("invalid file transfer request")
            inbox = Path.home() / "KyMoRem Inbox"
            inbox.mkdir(mode=0o700, parents=True, exist_ok=True)
            target = inbox / safe_filename(str(payload.get("name", "kymorem-file")))
            handle = target.open("wb")
            self.file_transfers[transfer_id] = {"path": target, "handle": handle, "size": size, "received": 0}
            link.send(frame("file_ack", transfer_id=transfer_id, state="begin", path=str(target)))
        elif kind == "file_chunk":
            transfer_id = str(payload.get("transfer_id", ""))
            transfer = self.file_transfers.get(transfer_id)
            if not transfer:
                raise RuntimeError("unknown file transfer")
            data = base64.b64decode(str(payload.get("data", "")), validate=True)
            transfer["received"] += len(data)
            if transfer["received"] > transfer["size"] or transfer["received"] > MAX_FILE_BYTES:
                raise RuntimeError("file transfer exceeds declared size")
            transfer["handle"].write(data)
        elif kind == "file_end":
            transfer_id = str(payload.get("transfer_id", ""))
            transfer = self.file_transfers.pop(transfer_id, None)
            if not transfer:
                raise RuntimeError("unknown file transfer")
            transfer["handle"].close()
            if transfer["received"] != transfer["size"]:
                raise RuntimeError("file transfer size mismatch")
            set_clipboard_files([transfer["path"]])
            link.send(frame("file_ack", transfer_id=transfer_id, state="complete", path=str(transfer["path"])))

    def send_file(self, link, path: Path) -> None:
        size = path.stat().st_size
        if size > MAX_FILE_BYTES:
            link.send(frame("error", message=f"file too large: {path.name}", event="file_transfer"))
            return
        transfer_id = uuid.uuid4().hex
        link.send(frame("file_begin", transfer_id=transfer_id, name=path.name, size=size))
        with path.open("rb") as handle:
            while True:
                chunk = handle.read(32768)
                if not chunk:
                    break
                link.send(frame("file_chunk", transfer_id=transfer_id, data=base64.b64encode(chunk).decode("ascii")))
        link.send(frame("file_end", transfer_id=transfer_id))

    def enter_from_edge(self, edge: str, x_ratio, y_ratio) -> tuple[int, int]:
        self.width, self.height = screen_size()
        max_x = max(0, self.width - 1)
        max_y = max(0, self.height - 1)
        x = clamp_axis(round(ratio(x_ratio) * max_x), max_x)
        y = clamp_axis(round(ratio(y_ratio) * max_y), max_y)
        if edge == "left":
            x = min(8, max_x)
        elif edge == "right":
            x = max(0, max_x - 8)
        elif edge == "up":
            y = min(8, max_y)
        elif edge == "down":
            y = max(0, max_y - 8)
        reset_cursor_shape()
        run_xdotool("mousemove", str(x), str(y))
        run_xdotool("mousemove_relative", "--", "1", "0")
        run_xdotool("mousemove_relative", "--", "-1", "0")
        self.pointer_x = x
        self.pointer_y = y
        reset_cursor_shape()
        focus_window_under_pointer()
        log(f"pointer entered from {edge} at {x},{y}")
        return x, y

    def move_pointer(self, dx: int, dy: int) -> None:
        if dx == 0 and dy == 0:
            return
        max_x = max(0, self.width - 1)
        max_y = max(0, self.height - 1)
        self.pointer_x = max(0, min(max_x, int(self.pointer_x) + int(dx)))
        self.pointer_y = max(0, min(max_y, int(self.pointer_y) + int(dy)))
        result = run_xdotool("mousemove", str(self.pointer_x), str(self.pointer_y))
        if result.returncode != 0:
            raise RuntimeError(result.stderr.strip() or "xdotool mousemove failed")

    def report_edge(self, link) -> None:
        try:
            x, y = pointer_location()
            self.pointer_x = x
            self.pointer_y = y
        except RuntimeError:
            x, y = self.pointer_x, self.pointer_y
        now = time.monotonic()
        edges = edge_names_from_pointer(x, y, self.width, self.height)
        active_edges = set(edges)
        self.last_edge_report = {
            edge: ts for edge, ts in self.last_edge_report.items() if edge in active_edges
        }
        for edge in edges:
            last = float(self.last_edge_report.get(edge, 0.0))
            if now - last < EDGE_REPORT_INTERVAL:
                continue
            self.last_edge_report[edge] = now
            link.send(frame("edge", edge=edge, x=x, y=y))

    def _verify_tools(self) -> None:
        for tool in ["xdotool", "xdpyinfo"]:
            if shutil.which(tool) is None:
                raise RuntimeError(f"{tool} is required")

    def _verify_session(self) -> None:
        session = os.environ.get("XDG_SESSION_TYPE", "").lower()
        if session == "wayland" and os.environ.get("KYMOREM_ALLOW_WAYLAND") != "1":
            raise RuntimeError(
                "Wayland session detected. KyMoRem v0.2.0-rc1 Linux client targets X11; "
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


def wheel_steps(value) -> int:
    try:
        delta = int(value)
    except (TypeError, ValueError):
        return 0
    steps = abs(delta) // WHEEL_DELTA_UNIT
    if steps == 0:
        return 0
    return min(MAX_WHEEL_STEPS_PER_FRAME, steps)


def edge_names_from_pointer(x: int, y: int, width: int, height: int) -> list[str]:
    max_x = max(0, width - 1)
    max_y = max(0, height - 1)
    edges: list[str] = []
    if x <= 1:
        edges.append("left")
    if x >= max_x - 1:
        edges.append("right")
    if y <= 1:
        edges.append("up")
    if y >= max_y - 1:
        edges.append("down")
    return edges


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


def main() -> int:
    parser = argparse.ArgumentParser(description="KyMoRem Linux client")
    parser.add_argument("--bind", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=PORT)
    parser.add_argument("--name", default=socket.gethostname())
    parser.add_argument("--token", default=None)
    parser.add_argument("--token-file", default=None)
    args = parser.parse_args()

    stop_running_instance()
    free_socket(args.port, "tcp")
    free_socket(DISCOVERY_PORT, "udp")
    resolved = None
    try:
        resolved = resolve_token(args)
        agent = ClientAgent(args.bind, args.port, args.name, resolved.value)
        agent.serve()
    except CryptoError as exc:
        message = str(exc)
        if resolved and resolved.source == "default":
            message = f"{message}; place kymorem-token.txt next to the executable or use --token-file"
        log(f"security configuration error: {message}")
        return 64
    except KeyboardInterrupt:
        return 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
