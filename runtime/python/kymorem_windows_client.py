#!/usr/bin/env python3
from __future__ import annotations

import argparse
import base64
import ctypes
import os
import queue
import re
import socket
import subprocess
import sys
import threading
import time
import uuid
from pathlib import Path

from kymorem_common import APP_AUTHOR, APP_NAME, DEFAULT_TOKEN, DISCOVERY_PORT, PORT, VERSION, ResolvedToken, discover_runtime_token, frame
from kymorem_crypto import CryptoError, secure_accept, validate_token
from kymorem_discovery import DiscoveryBeacon


user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32
shell32 = ctypes.windll.shell32
try:
    shcore = ctypes.windll.shcore
except OSError:
    shcore = None

CF_UNICODETEXT = 13
CF_HDROP = 15
GMEM_MOVEABLE = 0x0002
KEYEVENTF_KEYUP = 0x0002
MOUSEEVENTF_MOVE = 0x0001
MOUSEEVENTF_LEFTDOWN = 0x0002
MOUSEEVENTF_LEFTUP = 0x0004
MOUSEEVENTF_RIGHTDOWN = 0x0008
MOUSEEVENTF_RIGHTUP = 0x0010
MOUSEEVENTF_MIDDLEDOWN = 0x0020
MOUSEEVENTF_MIDDLEUP = 0x0040
MOUSEEVENTF_WHEEL = 0x0800
MOUSEEVENTF_HWHEEL = 0x01000
SM_XVIRTUALSCREEN = 76
SM_YVIRTUALSCREEN = 77
SM_CXVIRTUALSCREEN = 78
SM_CYVIRTUALSCREEN = 79

MAX_MOVE_DELTA = 4096
MAX_ACTIVE_SESSIONS = 4
MAX_FRAMES_PER_SECOND = 1200
MAX_CLIPBOARD_BYTES = 1024 * 1024
MAX_FILE_BYTES = 5 * 1024 * 1024
WHEEL_DELTA_UNIT = 120
MAX_WHEEL_STEPS_PER_FRAME = 4
SAFE_FILENAME = re.compile(r"[^A-Za-z0-9._ -]+")
FIREWALL_RULE_PREFIX = f"{APP_NAME} Win7 Client"
FALLBACK_RELEASE_KEYS = {
    "VK_LSHIFT",
    "VK_RSHIFT",
    "VK_LCONTROL",
    "VK_RCONTROL",
    "VK_LMENU",
    "VK_RMENU",
    "VK_LWIN",
    "VK_RWIN",
}

VK = {
    "VK_BACK": 0x08,
    "VK_TAB": 0x09,
    "VK_RETURN": 0x0D,
    "VK_ESCAPE": 0x1B,
    "VK_SPACE": 0x20,
    "VK_PRIOR": 0x21,
    "VK_NEXT": 0x22,
    "VK_END": 0x23,
    "VK_HOME": 0x24,
    "VK_LEFT": 0x25,
    "VK_UP": 0x26,
    "VK_RIGHT": 0x27,
    "VK_DOWN": 0x28,
    "VK_INSERT": 0x2D,
    "VK_DELETE": 0x2E,
    "VK_CAPITAL": 0x14,
    "VK_LWIN": 0x5B,
    "VK_RWIN": 0x5C,
    "VK_LSHIFT": 0xA0,
    "VK_RSHIFT": 0xA1,
    "VK_LCONTROL": 0xA2,
    "VK_RCONTROL": 0xA3,
    "VK_LMENU": 0xA4,
    "VK_RMENU": 0xA5,
    "VK_OEM_1": 0xBA,
    "VK_OEM_PLUS": 0xBB,
    "VK_OEM_COMMA": 0xBC,
    "VK_OEM_MINUS": 0xBD,
    "VK_OEM_PERIOD": 0xBE,
    "VK_OEM_2": 0xBF,
    "VK_OEM_3": 0xC0,
    "VK_OEM_4": 0xDB,
    "VK_OEM_5": 0xDC,
    "VK_OEM_6": 0xDD,
    "VK_OEM_7": 0xDE,
    **{f"VK_{chr(code)}": code for code in range(ord("A"), ord("Z") + 1)},
    **{f"VK_{n}": 0x30 + n for n in range(10)},
    **{f"VK_F{n}": 0x70 + n - 1 for n in range(1, 25)},
    **{f"VK_NUMPAD{n}": 0x60 + n for n in range(10)},
    "VK_MULTIPLY": 0x6A,
    "VK_ADD": 0x6B,
    "VK_SEPARATOR": 0x6C,
    "VK_SUBTRACT": 0x6D,
    "VK_DECIMAL": 0x6E,
    "VK_DIVIDE": 0x6F,
}

BUTTON_FLAGS = {
    "left": (MOUSEEVENTF_LEFTDOWN, MOUSEEVENTF_LEFTUP),
    "right": (MOUSEEVENTF_RIGHTDOWN, MOUSEEVENTF_RIGHTUP),
    "middle": (MOUSEEVENTF_MIDDLEDOWN, MOUSEEVENTF_MIDDLEUP),
}


class POINT(ctypes.Structure):
    _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]


def enable_dpi_awareness() -> None:
    if shcore:
        try:
            if shcore.SetProcessDpiAwareness(2) == 0:
                return
        except OSError:
            pass
    try:
        user32.SetProcessDPIAware()
    except OSError:
        pass


enable_dpi_awareness()


def runtime_dir() -> Path:
    path = Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "KyMoRem"
    path.mkdir(parents=True, exist_ok=True)
    return path


LOG_FILE = runtime_dir() / "windows-client.log"


def log(message: str) -> None:
    line = f"{time.strftime('%Y-%m-%d %H:%M:%S')} {message}"
    print(line, flush=True)
    try:
        with LOG_FILE.open("a", encoding="utf-8") as handle:
            handle.write(line + "\n")
    except OSError:
        pass


def is_loopback_bind(bind: str) -> bool:
    value = str(bind).strip().lower()
    return value in {"127.0.0.1", "localhost"}


def is_elevated() -> bool:
    try:
        return bool(shell32.IsUserAnAdmin())
    except OSError:
        return False


def ps_literal(value: str | Path) -> str:
    return str(value).replace("'", "''")


def run_text_command(command: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        errors="replace",
        check=False,
    )


def firewall_rule_names(port: int) -> list[str]:
    return [
        f"{FIREWALL_RULE_PREFIX} TCP {port}",
        f"{FIREWALL_RULE_PREFIX} UDP {DISCOVERY_PORT}",
    ]


def firewall_rule_commands(port: int, action: str) -> list[list[str]]:
    normalized = str(action).strip().lower()
    if normalized not in {"add", "delete"}:
        raise ValueError(f"unsupported firewall action: {action}")
    base = ["netsh", "advfirewall", "firewall", normalized, "rule"]
    rules = [
        (firewall_rule_names(port)[0], "TCP", port),
        (firewall_rule_names(port)[1], "UDP", DISCOVERY_PORT),
    ]
    commands: list[list[str]] = []
    for name, protocol, local_port in rules:
        command = [*base, f'name={name}', f'protocol={protocol}', f'localport={local_port}']
        if normalized == "add":
            command.extend(["dir=in", "action=allow", "enable=yes", "profile=private", "remoteip=LocalSubnet"])
        commands.append(command)
    return commands


def configure_firewall_rules(port: int, action: str) -> None:
    normalized = str(action).strip().lower()
    if normalized not in {"add", "delete"}:
        raise ValueError(f"unsupported firewall action: {action}")
    if not is_elevated():
        raise RuntimeError("administrator rights required to change Windows Firewall rules")
    for command in firewall_rule_commands(port, "delete"):
        run_text_command(command)
    if normalized == "delete":
        return
    for command in firewall_rule_commands(port, "add"):
        result = run_text_command(command)
        if result.returncode != 0:
            message = result.stderr.strip() or result.stdout.strip() or "netsh advfirewall failed"
            raise RuntimeError(message)


def firewall_rules_present(port: int) -> bool:
    for name in firewall_rule_names(port):
        result = run_text_command(["netsh", "advfirewall", "firewall", "show", "rule", f"name={name}"])
        output = f"{result.stdout}\n{result.stderr}"
        if name not in output:
            return False
    return True


def current_launch_target() -> tuple[str, list[str], str]:
    if getattr(sys, "frozen", False):
        executable = Path(sys.executable)
        return str(executable), [], str(executable.parent)
    script = Path(__file__).resolve()
    return sys.executable, [str(script)], str(script.parent)


def request_elevated_firewall_install(bind: str, port: int) -> bool:
    executable, prefix_args, working_dir = current_launch_target()
    args = [*prefix_args, "--install-firewall-rules", "--bind", bind, "--port", str(port)]
    arg_list = ", ".join(f"'{ps_literal(item)}'" for item in args)
    script = (
        f"$proc = Start-Process -FilePath '{ps_literal(executable)}' -ArgumentList @({arg_list}) "
        f"-WorkingDirectory '{ps_literal(working_dir)}' -Verb RunAs -Wait -PassThru; "
        "exit $proc.ExitCode"
    )
    result = run_text_command(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", script])
    return result.returncode == 0


def ensure_firewall_rules(bind: str, port: int) -> None:
    if is_loopback_bind(bind):
        return
    if firewall_rules_present(port):
        return
    log("Windows Firewall rules missing; requesting one-time private LAN access setup")
    if is_elevated():
        configure_firewall_rules(port, "add")
    else:
        if not request_elevated_firewall_install(bind, port):
            log("Windows Firewall rules were not installed automatically; Windows may still show a firewall prompt")
            return
    if firewall_rules_present(port):
        log(f"Windows Firewall ready on TCP {port} and UDP {DISCOVERY_PORT}")
        return
    log("Windows Firewall rules could not be verified; Windows may still show a firewall prompt")


def clamp_delta(value) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError):
        return 0
    return max(-MAX_MOVE_DELTA, min(MAX_MOVE_DELTA, number))


def clamp_wheel_delta(value) -> int:
    try:
        delta = int(value)
    except (TypeError, ValueError):
        return 0
    steps = int(delta / WHEEL_DELTA_UNIT)
    if steps == 0:
        return 0
    steps = max(-MAX_WHEEL_STEPS_PER_FRAME, min(MAX_WHEEL_STEPS_PER_FRAME, steps))
    return steps * WHEEL_DELTA_UNIT


def screen_size() -> tuple[int, int]:
    _left, _top, width, height = screen_rect()
    return width, height


def screen_rect() -> tuple[int, int, int, int]:
    left = int(user32.GetSystemMetrics(SM_XVIRTUALSCREEN))
    top = int(user32.GetSystemMetrics(SM_YVIRTUALSCREEN))
    width = int(user32.GetSystemMetrics(SM_CXVIRTUALSCREEN))
    height = int(user32.GetSystemMetrics(SM_CYVIRTUALSCREEN))
    if width <= 0 or height <= 0:
        return 0, 0, int(user32.GetSystemMetrics(0)), int(user32.GetSystemMetrics(1))
    return left, top, width, height


def pointer_location() -> tuple[int, int]:
    point = POINT()
    user32.GetCursorPos(ctypes.byref(point))
    return point.x, point.y


def move_pointer(dx: int, dy: int) -> None:
    if dx or dy:
        user32.mouse_event(MOUSEEVENTF_MOVE, int(dx), int(dy), 0, 0)


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


def enter_from_edge(edge: str, x_ratio, y_ratio) -> tuple[int, int, int, int]:
    left, top, width, height = screen_rect()
    max_x = max(0, width - 1)
    max_y = max(0, height - 1)
    x = left + clamp_axis(round(ratio(x_ratio) * max_x), max_x)
    y = top + clamp_axis(round(ratio(y_ratio) * max_y), max_y)
    if edge == "left":
        x = left + min(8, max_x)
    elif edge == "right":
        x = left + max(0, max_x - 8)
    elif edge == "up":
        y = top + min(8, max_y)
    elif edge == "down":
        y = top + max(0, max_y - 8)
    user32.SetCursorPos(int(x), int(y))
    move_pointer(1, 0)
    move_pointer(-1, 0)
    log(f"pointer entered from {edge} at {x},{y}")
    return x, y, width, height


def edge_names_from_pointer(x: int, y: int, left: int, top: int, width: int, height: int) -> list[str]:
    right = left + max(0, width - 1)
    bottom = top + max(0, height - 1)
    edges: list[str] = []
    if x <= left + 1:
        edges.append("left")
    if x >= right - 1:
        edges.append("right")
    if y <= top + 1:
        edges.append("up")
    if y >= bottom - 1:
        edges.append("down")
    return edges


def press_key(name: str, state: str) -> None:
    vk = VK.get(name)
    if not vk:
        return
    flags = KEYEVENTF_KEYUP if state == "up" else 0
    scan = user32.MapVirtualKeyW(vk, 0)
    user32.keybd_event(vk, scan, flags, 0)


def press_button(button: str, state: str) -> None:
    flags = BUTTON_FLAGS.get(button)
    if not flags:
        return
    user32.mouse_event(flags[0] if state == "down" else flags[1], 0, 0, 0, 0)


def release_inputs(keys: set[str], buttons: set[str]) -> None:
    for button in sorted(buttons | set(BUTTON_FLAGS)):
        press_button(button, "up")
    for name in sorted(keys | FALLBACK_RELEASE_KEYS):
        press_key(name, "up")


def get_clipboard_text() -> str:
    if not user32.OpenClipboard(None):
        raise RuntimeError("cannot open clipboard")
    try:
        handle = user32.GetClipboardData(CF_UNICODETEXT)
        if not handle:
            return ""
        ptr = kernel32.GlobalLock(handle)
        if not ptr:
            return ""
        try:
            return ctypes.wstring_at(ptr)[:MAX_CLIPBOARD_BYTES]
        finally:
            kernel32.GlobalUnlock(handle)
    finally:
        user32.CloseClipboard()


def set_clipboard_text(text: str) -> None:
    data = text[:MAX_CLIPBOARD_BYTES]
    if not user32.OpenClipboard(None):
        raise RuntimeError("cannot open clipboard")
    try:
        user32.EmptyClipboard()
        raw = data.encode("utf-16-le") + b"\x00\x00"
        handle = kernel32.GlobalAlloc(GMEM_MOVEABLE, len(raw))
        ptr = kernel32.GlobalLock(handle)
        ctypes.memmove(ptr, raw, len(raw))
        kernel32.GlobalUnlock(handle)
        user32.SetClipboardData(CF_UNICODETEXT, handle)
    finally:
        user32.CloseClipboard()


def clipboard_files() -> list[Path]:
    files: list[Path] = []
    if not user32.OpenClipboard(None):
        return files
    try:
        if not user32.IsClipboardFormatAvailable(CF_HDROP):
            return files
        handle = user32.GetClipboardData(CF_HDROP)
        count = shell32.DragQueryFileW(handle, 0xFFFFFFFF, None, 0)
        for index in range(count):
            length = shell32.DragQueryFileW(handle, index, None, 0)
            buffer = ctypes.create_unicode_buffer(length + 1)
            shell32.DragQueryFileW(handle, index, buffer, length + 1)
            path = Path(buffer.value)
            if path.is_file():
                files.append(path)
    finally:
        user32.CloseClipboard()
    return files


def safe_filename(name: str) -> str:
    cleaned = SAFE_FILENAME.sub("_", Path(name).name).strip(" .")
    return cleaned[:160] or "kymorem-file"


class WindowsClientAgent:
    def __init__(self, bind: str, port: int, name: str, token: str):
        validate_token(token)
        self.bind = bind
        self.port = port
        self.name = name
        self.token = token
        self.left, self.top, self.width, self.height = screen_rect()
        self.discovery = DiscoveryBeacon(token, "client", name, port)
        self.session_slots = threading.BoundedSemaphore(MAX_ACTIVE_SESSIONS)
        self.file_transfers: dict[str, dict] = {}
        self.active_keys: set[str] = set()
        self.active_buttons: set[str] = set()

    def serve(self) -> None:
        self.discovery.start()
        log(f"{APP_NAME} Windows client {VERSION} by {APP_AUTHOR} listening on {self.bind}:{self.port}")
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server:
                server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                server.bind((self.bind, self.port))
                server.listen(4)
                while True:
                    conn, addr = server.accept()
                    if not self.session_slots.acquire(blocking=False):
                        conn.close()
                        continue
                    threading.Thread(target=self.handle, args=(conn, addr), daemon=True).start()
        finally:
            self.discovery.close()

    def handle(self, conn: socket.socket, addr) -> None:
        try:
            with conn:
                try:
                    conn.settimeout(12)
                    link = secure_accept(
                        conn,
                        self.token,
                        {"role": "client", "name": self.name, "platform": "windows", "version": VERSION, "port": self.port},
                    )
                    conn.settimeout(None)
                    link.send(frame("hello", role="client", name=self.name, os="windows", width=self.width, height=self.height))
                    if str(link.peer.get("role", "")) != "health":
                        log(f"secure transport established with {addr[0]}:{addr[1]} using {link.suite}")
                except CryptoError as exc:
                    log(f"secure handshake rejected from {addr[0]}:{addr[1]}: {exc}")
                    return
                self.read_loop(link, addr)
        finally:
            self.session_slots.release()

    def read_loop(self, link, addr) -> None:
        window_start = time.monotonic()
        frame_count = 0
        for message in link.read_frames():
            now = time.monotonic()
            if now - window_start >= 1.0:
                window_start = now
                frame_count = 0
            frame_count += 1
            if frame_count > MAX_FRAMES_PER_SECOND:
                link.send(frame("error", message="rate limit exceeded", event="rate_limit"))
                break
            try:
                self.dispatch(link, message.get("type"), message.get("payload", {}))
            except Exception as exc:
                log(f"dispatch error: {exc}")
                link.send(frame("error", message=str(exc), event=message.get("type")))

    def dispatch(self, link, kind: str, payload: dict) -> None:
        if kind == "health_probe":
            link.send(frame("health_ack", name=self.name, os="windows", screen=f"{self.width}x{self.height}"))
        elif kind == "hello":
            link.send(frame("status", state="connected", name=self.name))
        elif kind == "pulse":
            move_pointer(36, 0)
            move_pointer(-36, 0)
            link.send(frame("pulse_ack", name=self.name))
        elif kind == "keepalive":
            link.send(frame("keepalive_ack", name=self.name, screen=f"{self.width}x{self.height}"))
        elif kind == "locate_pointer":
            x, y = pointer_location()
            link.send(frame("pointer_position", name=self.name, x=x, y=y, screen=f"{self.width}x{self.height}"))
        elif kind == "enter":
            edge = str(payload.get("edge", "left"))
            x, y, self.width, self.height = enter_from_edge(edge, payload.get("x_ratio"), payload.get("y_ratio"))
            self.left, self.top, self.width, self.height = screen_rect()
            link.send(frame("entered", name=self.name, edge=edge, x=x, y=y, screen=f"{self.width}x{self.height}"))
        elif kind == "move":
            move_pointer(clamp_delta(payload.get("dx", 0)), clamp_delta(payload.get("dy", 0)))
            self.report_edge(link)
        elif kind == "button":
            button = str(payload.get("button", "left"))
            state = str(payload.get("state", "up"))
            if state == "down":
                self.active_buttons.add(button)
            else:
                self.active_buttons.discard(button)
            press_button(button, state)
        elif kind == "wheel":
            dx = clamp_wheel_delta(payload.get("dx", 0))
            dy = clamp_wheel_delta(payload.get("dy", 0))
            if dy:
                user32.mouse_event(MOUSEEVENTF_WHEEL, 0, 0, dy, 0)
            if dx:
                user32.mouse_event(MOUSEEVENTF_HWHEEL, 0, 0, dx, 0)
        elif kind == "key":
            key = str(payload.get("key", ""))
            state = str(payload.get("state", "up"))
            if state == "down":
                self.active_keys.add(key)
            else:
                self.active_keys.discard(key)
            press_key(key, state)
        elif kind == "release":
            release_inputs(self.active_keys, self.active_buttons)
            self.active_keys.clear()
            self.active_buttons.clear()
            link.send(frame("released", name=self.name))
        elif kind == "clipboard_text":
            set_clipboard_text(str(payload.get("text", "")))
            link.send(frame("clipboard_ack", mode="text"))
        elif kind == "clipboard_request":
            link.send(frame("clipboard_text", text=get_clipboard_text(), source=self.name))
            if payload.get("files"):
                for path in clipboard_files():
                    self.send_file(link, path)
        elif kind == "file_begin":
            self.file_begin(payload)
        elif kind == "file_chunk":
            self.file_chunk(payload)
        elif kind == "file_end":
            self.file_end(link, payload)

    def report_edge(self, link) -> None:
        self.left, self.top, self.width, self.height = screen_rect()
        x, y = pointer_location()
        for edge in edge_names_from_pointer(x, y, self.left, self.top, self.width, self.height):
            link.send(frame("edge", edge=edge, x=x, y=y, left=self.left, top=self.top, width=self.width, height=self.height))

    def file_begin(self, payload: dict) -> None:
        transfer_id = str(payload.get("transfer_id", ""))
        size = int(payload.get("size", 0))
        if not transfer_id or size < 0 or size > MAX_FILE_BYTES:
            raise RuntimeError("invalid file transfer request")
        inbox = Path.home() / "Downloads" / "KyMoRem Inbox"
        inbox.mkdir(parents=True, exist_ok=True)
        target = inbox / safe_filename(str(payload.get("name", "kymorem-file")))
        self.file_transfers[transfer_id] = {"path": target, "handle": target.open("wb"), "size": size, "received": 0}

    def file_chunk(self, payload: dict) -> None:
        transfer_id = str(payload.get("transfer_id", ""))
        transfer = self.file_transfers.get(transfer_id)
        if not transfer:
            raise RuntimeError("unknown file transfer")
        data = base64.b64decode(str(payload.get("data", "")), validate=True)
        transfer["received"] += len(data)
        if transfer["received"] > transfer["size"] or transfer["received"] > MAX_FILE_BYTES:
            raise RuntimeError("file transfer exceeds declared size")
        transfer["handle"].write(data)

    def file_end(self, link, payload: dict) -> None:
        transfer_id = str(payload.get("transfer_id", ""))
        transfer = self.file_transfers.pop(transfer_id, None)
        if not transfer:
            raise RuntimeError("unknown file transfer")
        transfer["handle"].close()
        if transfer["received"] != transfer["size"]:
            raise RuntimeError("file transfer size mismatch")
        set_clipboard_text(str(transfer["path"]))
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
    parser = argparse.ArgumentParser(description="KyMoRem Windows 7 compatible client")
    parser.add_argument("--bind", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=PORT)
    parser.add_argument("--name", default=socket.gethostname())
    parser.add_argument("--token", default=None)
    parser.add_argument("--token-file", default=None)
    parser.add_argument("--install-firewall-rule", "--install-firewall-rules", dest="install_firewall_rules", action="store_true")
    parser.add_argument("--remove-firewall-rule", "--remove-firewall-rules", dest="remove_firewall_rules", action="store_true")
    args = parser.parse_args()
    resolved = None
    try:
        if args.install_firewall_rules and args.remove_firewall_rules:
            raise RuntimeError("choose either --install-firewall-rules or --remove-firewall-rules")
        if args.install_firewall_rules:
            if is_loopback_bind(args.bind):
                log("loopback bind does not require Windows Firewall rules")
                return 0
            configure_firewall_rules(args.port, "add")
            log(f"Windows Firewall rules installed for private LAN traffic on TCP {args.port} and UDP {DISCOVERY_PORT}")
            return 0
        if args.remove_firewall_rules:
            configure_firewall_rules(args.port, "delete")
            log(f"Windows Firewall rules removed for TCP {args.port} and UDP {DISCOVERY_PORT}")
            return 0
        resolved = resolve_token(args)
        ensure_firewall_rules(args.bind, args.port)
        WindowsClientAgent(args.bind, args.port, args.name, resolved.value).serve()
    except CryptoError as exc:
        message = str(exc)
        if resolved and resolved.source == "default":
            message = f"{message}; place kymorem-token.txt next to the executable or use --token-file"
        log(f"security configuration error: {message}")
        return 64
    except RuntimeError as exc:
        log(str(exc))
        return 65
    except KeyboardInterrupt:
        return 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
