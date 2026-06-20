import base64
import argparse
import ctypes
import json
import os
import queue
import re
import smtplib
import socket
import ssl
import sys
import threading
import time
import tkinter as tk
import uuid
from ctypes import wintypes
from email.message import EmailMessage
from email.utils import parseaddr
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from kymorem_common import APP_AUTHOR, APP_EXTENDED_NAME, APP_NAME, APP_SHORT_MARK, APP_SIGNATURE, DEFAULT_CONFIG, PORT, TEXT, VERSION, frame
from kymorem_crypto import CryptoError, secure_connect, validate_token
from kymorem_discovery import DiscoveryBeacon, DiscoveryListener

try:
    import pystray
    from PIL import Image
except ImportError:
    pystray = None
    Image = None


VK = {
    "VK_LBUTTON": 0x01,
    "VK_RBUTTON": 0x02,
    "VK_MBUTTON": 0x04,
    "VK_BACK": 0x08,
    "VK_TAB": 0x09,
    "VK_RETURN": 0x0D,
    "VK_SHIFT": 0x10,
    "VK_CONTROL": 0x11,
    "VK_MENU": 0x12,
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
    "VK_DELETE": 0x2E,
    "VK_INSERT": 0x2D,
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

BUTTON_KEYS = {
    "left": VK["VK_LBUTTON"],
    "right": VK["VK_RBUTTON"],
    "middle": VK["VK_MBUTTON"],
}

KEY_SCAN = {
    name: code
    for name, code in VK.items()
    if name not in {"VK_LBUTTON", "VK_RBUTTON", "VK_MBUTTON", "VK_SHIFT", "VK_CONTROL", "VK_MENU"}
}
VK_TO_KEY = {code: name for name, code in KEY_SCAN.items()}


class POINT(ctypes.Structure):
    _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]


user32 = ctypes.windll.user32
shell32 = ctypes.windll.shell32
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
try:
    shcore = ctypes.WinDLL("shcore", use_last_error=True)
except OSError:
    shcore = None

CF_HDROP = 15
ERROR_ALREADY_EXISTS = 183
SINGLE_INSTANCE_MUTEX = None
PROCESS_TERMINATE = 0x0001
TH32CS_SNAPPROCESS = 0x00000002
INVALID_HANDLE_VALUE = ctypes.c_void_p(-1).value
WH_KEYBOARD_LL = 13
WH_MOUSE_LL = 14
WM_QUIT = 0x0012
WM_KEYDOWN = 0x0100
WM_KEYUP = 0x0101
WM_SYSKEYDOWN = 0x0104
WM_SYSKEYUP = 0x0105
WM_MOUSEMOVE = 0x0200
WM_LBUTTONDOWN = 0x0201
WM_LBUTTONUP = 0x0202
WM_RBUTTONDOWN = 0x0204
WM_RBUTTONUP = 0x0205
WM_MBUTTONDOWN = 0x0207
WM_MBUTTONUP = 0x0208
WM_MOUSEWHEEL = 0x020A
WM_MOUSEHWHEEL = 0x020E
HOOKPROC = ctypes.WINFUNCTYPE(ctypes.c_long, ctypes.c_int, wintypes.WPARAM, wintypes.LPARAM)
MOUSE_BUTTON_MESSAGES = {
    WM_LBUTTONDOWN: ("left", "down"),
    WM_LBUTTONUP: ("left", "up"),
    WM_RBUTTONDOWN: ("right", "down"),
    WM_RBUTTONUP: ("right", "up"),
    WM_MBUTTONDOWN: ("middle", "down"),
    WM_MBUTTONUP: ("middle", "up"),
}


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


class PROCESSENTRY32W(ctypes.Structure):
    _fields_ = [
        ("dwSize", ctypes.c_ulong),
        ("cntUsage", ctypes.c_ulong),
        ("th32ProcessID", ctypes.c_ulong),
        ("th32DefaultHeapID", ctypes.c_void_p),
        ("th32ModuleID", ctypes.c_ulong),
        ("cntThreads", ctypes.c_ulong),
        ("th32ParentProcessID", ctypes.c_ulong),
        ("pcPriClassBase", ctypes.c_long),
        ("dwFlags", ctypes.c_ulong),
        ("szExeFile", ctypes.c_wchar * 260),
    ]


class KBDLLHOOKSTRUCT(ctypes.Structure):
    _fields_ = [
        ("vkCode", wintypes.DWORD),
        ("scanCode", wintypes.DWORD),
        ("flags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ctypes.c_void_p),
    ]


class MSLLHOOKSTRUCT(ctypes.Structure):
    _fields_ = [
        ("pt", POINT),
        ("mouseData", wintypes.DWORD),
        ("flags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ctypes.c_void_p),
    ]


kernel32.CreateToolhelp32Snapshot.argtypes = [ctypes.c_ulong, ctypes.c_ulong]
kernel32.CreateToolhelp32Snapshot.restype = ctypes.c_void_p
kernel32.Process32FirstW.argtypes = [ctypes.c_void_p, ctypes.POINTER(PROCESSENTRY32W)]
kernel32.Process32FirstW.restype = ctypes.c_bool
kernel32.Process32NextW.argtypes = [ctypes.c_void_p, ctypes.POINTER(PROCESSENTRY32W)]
kernel32.Process32NextW.restype = ctypes.c_bool
kernel32.OpenProcess.argtypes = [ctypes.c_ulong, ctypes.c_bool, ctypes.c_ulong]
kernel32.OpenProcess.restype = ctypes.c_void_p
kernel32.TerminateProcess.argtypes = [ctypes.c_void_p, ctypes.c_uint]
kernel32.TerminateProcess.restype = ctypes.c_bool
kernel32.CloseHandle.argtypes = [ctypes.c_void_p]
kernel32.CloseHandle.restype = ctypes.c_bool
kernel32.GetModuleHandleW.argtypes = [wintypes.LPCWSTR]
kernel32.GetModuleHandleW.restype = wintypes.HMODULE
kernel32.GetCurrentThreadId.argtypes = []
kernel32.GetCurrentThreadId.restype = wintypes.DWORD
user32.SetWindowsHookExW.argtypes = [ctypes.c_int, HOOKPROC, wintypes.HINSTANCE, wintypes.DWORD]
user32.SetWindowsHookExW.restype = wintypes.HHOOK
user32.CallNextHookEx.argtypes = [wintypes.HHOOK, ctypes.c_int, wintypes.WPARAM, wintypes.LPARAM]
user32.CallNextHookEx.restype = ctypes.c_long
user32.UnhookWindowsHookEx.argtypes = [wintypes.HHOOK]
user32.UnhookWindowsHookEx.restype = wintypes.BOOL
user32.GetMessageW.argtypes = [ctypes.POINTER(wintypes.MSG), wintypes.HWND, wintypes.UINT, wintypes.UINT]
user32.GetMessageW.restype = wintypes.BOOL
user32.TranslateMessage.argtypes = [ctypes.POINTER(wintypes.MSG)]
user32.TranslateMessage.restype = wintypes.BOOL
user32.DispatchMessageW.argtypes = [ctypes.POINTER(wintypes.MSG)]
user32.DispatchMessageW.restype = wintypes.LPARAM
user32.PostThreadMessageW.argtypes = [wintypes.DWORD, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
user32.PostThreadMessageW.restype = wintypes.BOOL
CYBER = {
    "bg": "#10141c",
    "bg2": "#151b26",
    "panel": "#1d2532",
    "panel2": "#263141",
    "line": "#465569",
    "text": "#f7fbff",
    "muted": "#b8c4d6",
    "cyan": "#45d6ff",
    "cyan_dim": "#27697c",
    "pink": "#d66bff",
    "pink_dim": "#5f3b73",
    "acid": "#8eea9f",
    "yellow": "#f4c95d",
    "red": "#ff6b7d",
}

THEMES = {
    "cyber_noir": CYBER.copy(),
    "dark": {
        **CYBER,
        "bg": "#111315",
        "bg2": "#171a1f",
        "panel": "#20242b",
        "panel2": "#2b3038",
        "line": "#3d4652",
        "text": "#f2f4f8",
        "muted": "#aeb7c4",
        "cyan": "#64d2ff",
        "pink": "#9aa8ff",
        "acid": "#6ee7b7",
    },
    "white": {
        **CYBER,
        "bg": "#f6f8fb",
        "bg2": "#ffffff",
        "panel": "#ffffff",
        "panel2": "#e8edf5",
        "line": "#c8d2e1",
        "text": "#172033",
        "muted": "#5f6f84",
        "cyan": "#006fbf",
        "cyan_dim": "#99c9f2",
        "pink": "#8a3ffc",
        "pink_dim": "#d7c6ff",
        "acid": "#168a4a",
        "yellow": "#8a6400",
        "red": "#c73535",
    },
    "old_school_x11": {
        **CYBER,
        "bg": "#eef1f6",
        "bg2": "#f8fafc",
        "panel": "#ffffff",
        "panel2": "#dbe4ef",
        "line": "#9aaec5",
        "text": "#1f2937",
        "muted": "#65758b",
        "cyan": "#2563eb",
        "cyan_dim": "#bfdbfe",
        "pink": "#475569",
        "pink_dim": "#cbd5e1",
        "acid": "#15803d",
        "yellow": "#b45309",
        "red": "#b91c1c",
    },
    "old_school_x11": {
        **CYBER,
        "bg": "#b8b8b8",
        "bg2": "#c0c0c0",
        "panel": "#d0d0d0",
        "panel2": "#a8a8a8",
        "line": "#404040",
        "text": "#000000",
        "muted": "#303030",
        "cyan": "#000080",
        "cyan_dim": "#6060a0",
        "pink": "#800000",
        "pink_dim": "#a06060",
        "acid": "#006000",
        "yellow": "#806000",
        "red": "#a00000",
    },
    "windows_xp": {
        **CYBER,
        "bg": "#ece9d8",
        "bg2": "#ffffff",
        "panel": "#f4f2e8",
        "panel2": "#d6dff7",
        "line": "#7f9db9",
        "text": "#000000",
        "muted": "#4b5563",
        "cyan": "#0a246a",
        "cyan_dim": "#6b8fd6",
        "pink": "#316ac5",
        "pink_dim": "#b8c7e8",
        "acid": "#008000",
        "yellow": "#996600",
        "red": "#cc0000",
    },
    "accessible": {
        **CYBER,
        "bg": "#000000",
        "bg2": "#000000",
        "panel": "#111111",
        "panel2": "#222222",
        "line": "#ffffff",
        "text": "#ffffff",
        "muted": "#d0d0d0",
        "cyan": "#00ffff",
        "cyan_dim": "#80ffff",
        "pink": "#ffff00",
        "pink_dim": "#ffff80",
        "acid": "#00ff66",
        "yellow": "#ffff00",
        "red": "#ff5555",
    },
}

MODE_LABELS = {"client": "Client", "server": "Server"}
MODE_VALUES = {value: key for key, value in MODE_LABELS.items()}
LANG_LABELS = {"it": "IT=Italiano", "en": "EN=English", "ch": "CH=Swiss"}
LANG_VALUES = {value: key for key, value in LANG_LABELS.items()}
THEME_LABELS = {key: key.replace("_", " ").title() for key in THEMES}
THEME_VALUES = {value: key for key, value in THEME_LABELS.items()}

POSITION_TO_GRID = {
    "left": (-1, 0),
    "right": (1, 0),
    "up": (0, -1),
    "down": (0, 1),
}
GRID_TO_POSITION = {value: key for key, value in POSITION_TO_GRID.items()}
RETURN_EDGE = {"right": "left", "left": "right", "up": "down", "down": "up"}
MAX_CLIENTS = 9
MIN_EDGE_INTERVAL = 0.45
RELEASE_EDGE_MARGIN = 32
SAFE_FILENAME = re.compile(r"[^A-Za-z0-9._ -]+")


def get_cursor() -> tuple[int, int]:
    point = POINT()
    user32.GetCursorPos(ctypes.byref(point))
    return point.x, point.y


def set_cursor(x: int, y: int) -> None:
    user32.SetCursorPos(int(x), int(y))


def async_down(vk: int) -> bool:
    return bool(user32.GetAsyncKeyState(vk) & 0x8000)


def screen_size() -> tuple[int, int]:
    return user32.GetSystemMetrics(0), user32.GetSystemMetrics(1)


def windows_clipboard_files() -> list[Path]:
    files: list[Path] = []
    if not user32.OpenClipboard(None):
        return files
    try:
        if not user32.IsClipboardFormatAvailable(CF_HDROP):
            return files
        handle = user32.GetClipboardData(CF_HDROP)
        if not handle:
            return files
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


def local_ip_hint() -> str:
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.connect(("192.0.2.1", 9))
            return sock.getsockname()[0]
    except OSError:
        return "local-host"


def app_dir() -> Path:
    base = os.environ.get("APPDATA") or str(Path.home())
    path = Path(base) / "KyMoRem"
    path.mkdir(parents=True, exist_ok=True)
    return path


def acquire_single_instance() -> bool:
    global SINGLE_INSTANCE_MUTEX
    handle = kernel32.CreateMutexW(None, True, "Local\\KyMoRem.MainUI.okno")
    if not handle:
        return True
    if ctypes.get_last_error() == ERROR_ALREADY_EXISTS:
        kernel32.CloseHandle(handle)
        return False
    SINGLE_INSTANCE_MUTEX = handle
    return True


def _process_rows() -> list[tuple[int, int, str]]:
    rows: list[tuple[int, int, str]] = []
    snapshot = kernel32.CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0)
    if not snapshot or snapshot == INVALID_HANDLE_VALUE:
        return rows
    entry = PROCESSENTRY32W()
    entry.dwSize = ctypes.sizeof(PROCESSENTRY32W)
    try:
        ok = kernel32.Process32FirstW(snapshot, ctypes.byref(entry))
        while ok:
            rows.append((int(entry.th32ProcessID), int(entry.th32ParentProcessID), str(entry.szExeFile)))
            ok = kernel32.Process32NextW(snapshot, ctypes.byref(entry))
    finally:
        kernel32.CloseHandle(snapshot)
    return rows


def _parent_pid(pid: int) -> int:
    for item_pid, parent, _name in _process_rows():
        if item_pid == pid:
            return parent
    return 0


def terminate_previous_instances() -> int:
    current_pid = os.getpid()
    current_parent = _parent_pid(current_pid)
    keep = {current_pid, current_parent}
    killed = 0
    for pid, _parent, name in _process_rows():
        if pid in keep or name.lower() != "kymorem.exe":
            continue
        handle = kernel32.OpenProcess(PROCESS_TERMINATE, False, pid)
        if not handle:
            continue
        try:
            if kernel32.TerminateProcess(handle, 0):
                killed += 1
        finally:
            kernel32.CloseHandle(handle)
    if killed:
        time.sleep(0.8)
    return killed


def client_key(client: dict) -> str:
    return f"{client.get('host', '')}:{int(client.get('port', PORT))}"


def grid_from_position(position: str) -> tuple[int, int]:
    return POSITION_TO_GRID.get(str(position), (1, 0))


def position_from_grid(x: int, y: int) -> str:
    if (x, y) in GRID_TO_POSITION:
        return GRID_TO_POSITION[(x, y)]
    if abs(x) >= abs(y):
        return "right" if x >= 0 else "left"
    return "down" if y >= 0 else "up"


def normalize_client(raw: dict, index: int = 0) -> dict:
    client = dict(raw or {})
    if not client.get("name"):
        client["name"] = f"client-{index + 1}"
    if not client.get("host"):
        client["host"] = "127.0.0.1"
    try:
        client["port"] = int(client.get("port", PORT))
    except (TypeError, ValueError):
        client["port"] = PORT
    if "x" not in client or "y" not in client:
        gx, gy = grid_from_position(str(client.get("position", "right")))
        client["x"] = gx
        client["y"] = gy
    try:
        client["x"] = max(-4, min(4, int(client.get("x", 1))))
        client["y"] = max(-4, min(4, int(client.get("y", 0))))
    except (TypeError, ValueError):
        client["x"], client["y"] = 1, 0
    if client["x"] == 0 and client["y"] == 0:
        client["x"] = 1
    client["position"] = position_from_grid(client["x"], client["y"])
    client["enabled"] = bool(client.get("enabled", True))
    client["source"] = str(client.get("source", "manual"))
    return client


def next_free_position(clients: list[dict]) -> tuple[int, int]:
    occupied = {(int(item.get("x", 0)), int(item.get("y", 0))) for item in clients}
    candidates = [(1, 0), (-1, 0), (0, 1), (0, -1), (2, 0), (-2, 0), (0, 2), (0, -2), (1, 1)]
    return next((candidate for candidate in candidates if candidate not in occupied), (len(clients) + 1, 0))


def load_config() -> dict:
    path = app_dir() / "config.json"
    if not path.exists():
        path.write_text(json.dumps(DEFAULT_CONFIG, indent=2), encoding="utf-8")
    with path.open("r", encoding="utf-8-sig") as handle:
        config = json.load(handle)
    changed = False
    for key, value in DEFAULT_CONFIG.items():
        if key not in config:
            config[key] = value
            changed = True
    for key in ["security", "clipboard", "discovery", "email_relay"]:
        merged = dict(DEFAULT_CONFIG[key])
        merged.update(config.get(key, {}))
        if merged != config.get(key):
            config[key] = merged
            changed = True
    layout = dict(DEFAULT_CONFIG["layout"])
    layout.update(config.get("layout", {}))
    if layout != config.get("layout"):
        config["layout"] = layout
        changed = True
    normalized_clients = [normalize_client(item, index) for index, item in enumerate(config.get("clients", []))]
    if not normalized_clients:
        normalized_clients = [normalize_client(DEFAULT_CONFIG["clients"][0])]
    if normalized_clients != config.get("clients"):
        config["clients"] = normalized_clients
        changed = True
    if config.get("language") not in TEXT:
        config["language"] = "ch"
        changed = True
    if config.get("mode") not in {"server", "client"}:
        config["mode"] = "client"
        changed = True
    raw_server_on = config.get("server_on", False)
    if isinstance(raw_server_on, str):
        raw_server_on = raw_server_on.strip().lower() in {"1", "true", "yes", "on"}
    normalized_server_on = bool(raw_server_on and config.get("mode") == "server")
    if normalized_server_on != config.get("server_on"):
        config["server_on"] = normalized_server_on
        changed = True
    if config.get("theme") not in THEMES:
        config["theme"] = "old_school_x11"
        changed = True
    if changed:
        path.write_text(json.dumps(config, indent=2), encoding="utf-8")
    return config


def asset_path(name: str) -> Path:
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
    direct = base / "assets" / name
    if direct.exists():
        return direct
    return Path(__file__).resolve().parent / "assets" / name


class RemoteLink:
    def __init__(self, events: queue.Queue):
        self.events = events
        self.sock: socket.socket | None = None
        self.secure = None
        self.lock = threading.Lock()
        self.send_lock = threading.Lock()
        self.connected = False
        self.connecting = False
        self.client_info: dict = {}
        self.endpoint: tuple[str, int] | None = None

    def connect(self, host: str, port: int, token: str, identity: dict) -> None:
        self.disconnect()
        with self.lock:
            if self.connected or self.connecting:
                return
            self.connecting = True
        thread = threading.Thread(target=self._connect_thread, args=(host, port, token, identity), daemon=True)
        thread.start()

    def _connect_thread(self, host: str, port: int, token: str, identity: dict) -> None:
        try:
            self.events.put(("log", f"Connessione a {host}:{port}..."))
            sock = socket.create_connection((host, port), timeout=5)
            sock.settimeout(None)
            secure = secure_connect(sock, token, identity)
            with self.lock:
                self.sock = sock
                self.secure = secure
                self.connected = True
                self.endpoint = (host, int(port))
            secure.send(frame("hello", role="server", name=identity.get("name", "Windows"), version=VERSION))
            self.events.put(("log", f"Connesso a {host}:{port} // {secure.suite}"))
            self.events.put(("relay", ("client_connected", f"KyMoRem client connected: {host}:{port}", f"Secure suite: {secure.suite}")))
            for message in secure.read_frames():
                self.events.put(("frame", message))
        except CryptoError as exc:
            self.events.put(("log", f"Sicurezza handshake fallita: {exc}"))
            self.events.put(("relay", ("security_error", "KyMoRem secure handshake failed", str(exc))))
        except Exception as exc:
            self.events.put(("log", f"Connessione fallita: {exc}"))
        finally:
            with self.lock:
                was_connected = self.connected
                self.connecting = False
                self.connected = False
                self.sock = None
                self.secure = None
                self.endpoint = None
            if was_connected:
                self.events.put(("relay", ("client_disconnected", f"KyMoRem client disconnected: {host}:{port}", "The secure transport has closed.")))
            self.events.put(("disconnected", None))

    def disconnect(self) -> None:
        with self.lock:
            sock = self.sock
            secure = self.secure
            self.sock = None
            self.secure = None
            self.connected = False
            self.connecting = False
            self.endpoint = None
        if sock:
            try:
                if secure:
                    secure.send(frame("release"))
                sock.close()
            except Exception:
                pass

    def send(self, kind: str, **payload) -> None:
        with self.lock:
            secure = self.secure
        if not secure:
            return
        try:
            with self.send_lock:
                secure.send(frame(kind, **payload))
        except Exception as exc:
            self.events.put(("log", f"Invio fallito: {exc}"))
            self.disconnect()


class ThemedSelect(tk.Button):
    def __init__(self, parent, values, width=14, textvariable=None):
        self.variable = textvariable or tk.StringVar(value=values[0] if values else "")
        self.callbacks = []
        self.values = list(values)
        self.popup = None
        super().__init__(
            parent,
            textvariable=self.variable,
            command=self._toggle_popup,
            width=width,
            anchor="w",
            justify="left",
            bg=CYBER["panel2"],
            fg=CYBER["text"],
            activebackground=CYBER["cyan_dim"],
            activeforeground=CYBER["text"],
            highlightthickness=1,
            highlightbackground=CYBER["cyan"],
            highlightcolor=CYBER["cyan"],
            relief="flat",
            padx=8,
            pady=2,
            font=("Consolas", 10, "bold"),
        )

    def bind(self, sequence=None, func=None, add=None):
        if sequence == "<<ComboboxSelected>>" and func is not None:
            self.callbacks.append(func)
            return None
        return super().bind(sequence, func, add)

    def set_values(self, values) -> None:
        self.values = list(values)

    def _toggle_popup(self, _event=None):
        if self.popup and self.popup.winfo_exists():
            self._close_popup()
        else:
            self._open_popup()
        return "break"

    def _open_popup(self) -> None:
        self._close_popup()
        popup = tk.Toplevel(self)
        self.popup = popup
        popup.overrideredirect(True)
        popup.configure(bg=CYBER["line"])
        popup.transient(self.winfo_toplevel())
        try:
            popup.attributes("-topmost", True)
        except tk.TclError:
            pass
        width = max(self.winfo_width(), 180)
        x = self.winfo_pointerx()
        y = self.winfo_pointery() + self.winfo_height() + 4
        popup.geometry(f"{width}x{max(1, len(self.values)) * 28}+{x}+{y}")
        for value in self.values:
            row = tk.Label(
                popup,
                text=value,
                anchor="w",
                bg=CYBER["panel2"],
                fg=CYBER["text"],
                padx=10,
                pady=5,
                font=("Consolas", 10, "bold"),
            )
            row.pack(fill="x", padx=1, pady=(1, 0))
            row.bind("<Enter>", lambda _event, widget=row: widget.configure(bg=CYBER["cyan_dim"], fg=CYBER["text"]))
            row.bind("<Leave>", lambda _event, widget=row: widget.configure(bg=CYBER["panel2"], fg=CYBER["text"]))
            row.bind("<Button-1>", lambda _event, item=value: self._select(item))
        popup.bind("<Escape>", lambda _event: self._close_popup())
        popup.focus_force()

    def _close_popup(self) -> None:
        if self.popup and self.popup.winfo_exists():
            self.popup.destroy()
        self.popup = None

    def _select(self, value) -> None:
        self.variable.set(value)
        self._close_popup()
        for callback in list(self.callbacks):
            callback(None)

    def get(self):
        return self.variable.get()

    def set(self, value) -> None:
        self.variable.set(value)


class ControlEngine:
    def __init__(self, link: RemoteLink, events: queue.Queue, router=None, enabled: bool = False):
        self.link = link
        self.events = events
        self.router = router
        self.enabled = enabled
        self.remote = False
        self.running = True
        self.w, self.h = screen_size()
        self.anchor = (self.w // 2, self.h // 2)
        self.active_direction = "right"
        self.last_edge_ts = 0.0
        self.edge_exit = {
            "direction": "right",
            "x": self.w - 1,
            "y": self.h // 2,
            "x_ratio": 1.0,
            "y_ratio": 0.5,
            "ts": 0.0,
        }
        self.cursor_hidden = False
        self.keyboard_hook = None
        self.mouse_hook = None
        self.hook_thread_id = 0
        self.hook_ctrl_down = False
        self.hook_shift_down = False
        self.hook_esc_down = False
        self.last_pointer_find_ts = 0.0
        self.keyboard_proc = HOOKPROC(self._keyboard_hook)
        self.mouse_proc = HOOKPROC(self._mouse_hook)
        self.button_state = {name: False for name in BUTTON_KEYS}
        self.key_state = {name: False for name in KEY_SCAN}
        self.input_queue: queue.Queue = queue.Queue(maxsize=4096)
        self.input_thread = threading.Thread(target=self._input_sender_loop, daemon=True)
        self.input_thread.start()
        self.hook_thread = threading.Thread(target=self._hook_loop, daemon=True)
        self.hook_thread.start()
        self.thread = threading.Thread(target=self.loop, daemon=True)
        self.thread.start()

    def _queue_remote(self, kind: str, **payload) -> None:
        try:
            self.input_queue.put_nowait((kind, payload))
        except queue.Full:
            self.events.put(("log", "Input remoto scartato: coda piena."))

    def _input_sender_loop(self) -> None:
        while self.running:
            try:
                kind, payload = self.input_queue.get(timeout=0.1)
            except queue.Empty:
                continue
            if self.remote:
                self.link.send(kind, **payload)

    def _send_remote_key_state(self, vk: int, down: bool) -> None:
        key = VK_TO_KEY.get(vk)
        if not key:
            return
        if self.key_state.get(key) == down:
            return
        self.key_state[key] = down
        self._queue_remote("key", key=key, state="down" if down else "up")

    def _release_remote_inputs(self) -> None:
        for key, down in list(self.key_state.items()):
            if down:
                self.key_state[key] = False
                self.link.send("key", key=key, state="up")
        for button, down in list(self.button_state.items()):
            if down:
                self.button_state[button] = False
                self.link.send("button", button=button, state="up")

    def _keyboard_hook(self, n_code, w_param, l_param):
        if n_code >= 0:
            info = ctypes.cast(l_param, ctypes.POINTER(KBDLLHOOKSTRUCT)).contents
            vk = int(info.vkCode)
            msg = int(w_param)
            if msg in {WM_KEYDOWN, WM_SYSKEYDOWN}:
                if vk in {VK["VK_CONTROL"], VK["VK_LCONTROL"], VK["VK_RCONTROL"]}:
                    self.hook_ctrl_down = True
                elif vk in {VK["VK_SHIFT"], VK["VK_LSHIFT"], VK["VK_RSHIFT"]}:
                    self.hook_shift_down = True
                elif vk == VK["VK_ESCAPE"]:
                    self.hook_esc_down = True
                elif vk == VK["VK_M"] and self.hook_ctrl_down and self.hook_shift_down:
                    now = time.monotonic()
                    if now - self.last_pointer_find_ts > 0.6:
                        self.last_pointer_find_ts = now
                        self.find_pointer()
                    return 1
                if self.hook_ctrl_down and self.hook_esc_down:
                    self.release()
                    return 1
                if self.remote:
                    self._send_remote_key_state(vk, True)
                    return 1
            elif msg in {WM_KEYUP, WM_SYSKEYUP}:
                if vk in {VK["VK_CONTROL"], VK["VK_LCONTROL"], VK["VK_RCONTROL"]}:
                    self.hook_ctrl_down = False
                elif vk in {VK["VK_SHIFT"], VK["VK_LSHIFT"], VK["VK_RSHIFT"]}:
                    self.hook_shift_down = False
                elif vk == VK["VK_ESCAPE"]:
                    self.hook_esc_down = False
                if self.remote:
                    self._send_remote_key_state(vk, False)
                    return 1
        return user32.CallNextHookEx(self.keyboard_hook, n_code, w_param, l_param)

    def _mouse_hook(self, n_code, w_param, l_param):
        if n_code >= 0 and self.remote:
            msg = int(w_param)
            if msg == WM_MOUSEMOVE:
                return user32.CallNextHookEx(self.mouse_hook, n_code, w_param, l_param)
            if msg in MOUSE_BUTTON_MESSAGES:
                button, state = MOUSE_BUTTON_MESSAGES[msg]
                down = state == "down"
                if self.button_state.get(button) != down:
                    self.button_state[button] = down
                    self._queue_remote("button", button=button, state=state)
                return 1
            if msg in {WM_MOUSEWHEEL, WM_MOUSEHWHEEL}:
                info = ctypes.cast(l_param, ctypes.POINTER(MSLLHOOKSTRUCT)).contents
                delta = ctypes.c_short((int(info.mouseData) >> 16) & 0xFFFF).value
                if delta:
                    self._queue_remote("wheel", dy=delta)
                return 1
        return user32.CallNextHookEx(self.mouse_hook, n_code, w_param, l_param)

    def _hook_loop(self) -> None:
        self.hook_thread_id = int(kernel32.GetCurrentThreadId())
        module = kernel32.GetModuleHandleW(None)
        self.keyboard_hook = user32.SetWindowsHookExW(WH_KEYBOARD_LL, self.keyboard_proc, module, 0)
        self.mouse_hook = user32.SetWindowsHookExW(WH_MOUSE_LL, self.mouse_proc, module, 0)
        msg = wintypes.MSG()
        while self.running and user32.GetMessageW(ctypes.byref(msg), None, 0, 0) != 0:
            user32.TranslateMessage(ctypes.byref(msg))
            user32.DispatchMessageW(ctypes.byref(msg))
        if self.keyboard_hook:
            user32.UnhookWindowsHookEx(self.keyboard_hook)
            self.keyboard_hook = None
        if self.mouse_hook:
            user32.UnhookWindowsHookEx(self.mouse_hook)
            self.mouse_hook = None

    def find_pointer(self) -> None:
        x, y = get_cursor()
        if self.remote:
            self.link.send("locate_pointer")
        self.events.put(
            (
                "pointer",
                {
                    "scope": "remote" if self.remote else "server",
                    "x": x,
                    "y": y,
                    "screen": f"{self.w}x{self.h}",
                    "direction": self.active_direction,
                },
            )
        )

    def stop(self) -> None:
        self.running = False
        if self.hook_thread_id:
            user32.PostThreadMessageW(self.hook_thread_id, WM_QUIT, 0, 0)

    def _capture_edge_exit(self, direction: str, x: int, y: int) -> dict:
        self.w, self.h = screen_size()
        entry = {
            "direction": direction,
            "x": int(x),
            "y": int(y),
            "x_ratio": max(0.0, min(1.0, x / max(1, self.w - 1))),
            "y_ratio": max(0.0, min(1.0, y / max(1, self.h - 1))),
            "ts": time.monotonic(),
        }
        self.edge_exit = entry
        return dict(entry)

    def take(self, direction: str = "right", entry: dict | None = None) -> None:
        if not self.enabled:
            self.events.put(("log", "Server OFF: controllo remoto non attivo."))
            return
        if not self.link.connected:
            self.events.put(("log", "Nessun client connesso."))
            return
        context = entry
        if not context or context.get("direction") != direction:
            context = self.edge_exit if self.edge_exit.get("direction") == direction else None
        if not context or time.monotonic() - float(context.get("ts", 0.0)) > 8.0:
            x, y = get_cursor()
            context = self._capture_edge_exit(direction, x, y)
        entry_edge = RETURN_EDGE.get(direction, "left")
        x_ratio = float(context.get("x_ratio", 0.5))
        y_ratio = float(context.get("y_ratio", 0.5))
        self.active_direction = direction
        self.remote = True
        self.link.send(
            "enter",
            edge=entry_edge,
            source_edge=direction,
            source_x=int(context.get("x", 0)),
            source_y=int(context.get("y", 0)),
            x_ratio=x_ratio,
            y_ratio=y_ratio,
        )
        set_cursor(*self.anchor)
        self.events.put(("remote", True))
        self.events.put(
            (
                "log",
                f"Controllo remoto attivo verso {direction}: ingresso client da {entry_edge} "
                f"source={int(context.get('x', 0))},{int(context.get('y', 0))} "
                f"ratio={x_ratio:.3f},{y_ratio:.3f}. Ctrl+Esc rilascia.",
            )
        )

    def release(self) -> None:
        if self.remote:
            self.remote = False
            self._release_remote_inputs()
            self.last_edge_ts = time.monotonic()
            if self.active_direction == "left":
                set_cursor(RELEASE_EDGE_MARGIN, self.h // 2)
            elif self.active_direction == "up":
                set_cursor(self.w // 2, RELEASE_EDGE_MARGIN)
            elif self.active_direction == "down":
                set_cursor(self.w // 2, max(0, self.h - RELEASE_EDGE_MARGIN))
            else:
                set_cursor(max(0, self.w - RELEASE_EDGE_MARGIN), self.h // 2)
            self.link.send("release")
            self.events.put(("remote", False))
            self.events.put(("log", "Controllo remoto rilasciato."))

    def client_edge(self, edge: str) -> None:
        if RETURN_EDGE.get(self.active_direction, "left") == edge:
            self.release()

    def _host_edge(self, x: int, y: int) -> str | None:
        if x >= self.w - 2:
            return "right"
        if x <= 1:
            return "left"
        if y <= 1:
            return "up"
        if y >= self.h - 2:
            return "down"
        return None

    def loop(self) -> None:
        while self.running:
            time.sleep(0.012)
            if not self.enabled:
                continue
            if not self.remote:
                x, y = get_cursor()
                direction = self._host_edge(x, y)
                if direction and time.monotonic() - self.last_edge_ts > MIN_EDGE_INTERVAL:
                    self.last_edge_ts = time.monotonic()
                    entry = self._capture_edge_exit(direction, x, y)
                    if self.router and self.router(direction, entry):
                        self.take(direction, entry)
                continue

            if async_down(VK["VK_CONTROL"]) and async_down(VK["VK_ESCAPE"]):
                self.release()
                time.sleep(0.2)
                continue

            x, y = get_cursor()
            dx = x - self.anchor[0]
            dy = y - self.anchor[1]
            if dx or dy:
                self.link.send("move", dx=dx, dy=dy)
                set_cursor(*self.anchor)


class KyMoRemApp:
    def __init__(self) -> None:
        self.config = load_config()
        self.lang = self.config.get("language", "it")
        self.text = TEXT.get(self.lang, TEXT["it"])
        self.theme_id = str(self.config.get("theme", "old_school_x11"))
        CYBER.update(THEMES.get(self.theme_id, THEMES["old_school_x11"]))
        self.local_ip = local_ip_hint()
        self.discovered_clients: dict[str, dict] = {}
        self.client_boxes: dict[str, tuple[int, int, int, int]] = {}
        self.selected_client = ""
        self.selected_client = client_key(self._client_config())
        self.drag_client: str | None = None
        self.file_transfers: dict[str, dict] = {}
        self.pointer_hint: dict | None = None
        self.pointer_hint_until = 0.0
        self.events: queue.Queue = queue.Queue()
        self.link = RemoteLink(self.events)
        self.server_active = bool(self.config.get("mode") == "server" and self.config.get("server_on", False))
        self.auto_retry_started = False
        self.pending_take_direction: str | None = None
        self.pending_take_entry: dict | None = None
        self.engine = ControlEngine(self.link, self.events, self._route_from_edge, enabled=self.server_active)
        self.discovery_beacon = None
        self.discovery_listener = None
        self.tray_icon = None
        self.root = tk.Tk()
        self.root.title(f"{APP_NAME} {VERSION} // {APP_SHORT_MARK} Neon Route Console")
        self.root.geometry("1024x768")
        self.root.minsize(760, 500)
        self.root.configure(bg=CYBER["bg"])
        icon = asset_path("kymorem.ico")
        if icon.exists():
            try:
                self.root.iconbitmap(str(icon))
            except tk.TclError:
                pass
        self.root.protocol("WM_DELETE_WINDOW", self._hide_to_tray)
        self._style()
        self._build()
        self._start_tray()
        self._tick()
        if self.server_active:
            self._start_discovery()
            self._auto_connect()
        else:
            self._log("Modalita client predefinita: server OFF. Usa SERVER ON dalla UI per condividere mouse e tastiera.")

    def _style(self) -> None:
        style = ttk.Style()
        style.theme_use("clam")
        self.root.option_add("*TCombobox*Listbox.background", CYBER["panel2"])
        self.root.option_add("*TCombobox*Listbox.foreground", CYBER["text"])
        self.root.option_add("*TCombobox*Listbox.selectBackground", CYBER["cyan_dim"])
        self.root.option_add("*TCombobox*Listbox.selectForeground", CYBER["text"])
        self.root.option_add("*TCombobox*Listbox.font", "Consolas 10")
        style.configure(
            "Kmr.TCombobox",
            fieldbackground=CYBER["panel2"],
            background=CYBER["panel2"],
            foreground=CYBER["text"],
            bordercolor=CYBER["cyan"],
            lightcolor=CYBER["line"],
            darkcolor=CYBER["line"],
            arrowcolor=CYBER["cyan"],
            insertcolor=CYBER["text"],
            selectbackground=CYBER["pink_dim"],
            selectforeground=CYBER["text"],
            padding=3,
            arrowsize=14,
        )
        style.map(
            "Kmr.TCombobox",
            fieldbackground=[("readonly", CYBER["panel2"]), ("disabled", CYBER["panel"])],
            background=[("readonly", CYBER["panel2"]), ("active", CYBER["cyan_dim"])],
            foreground=[("readonly", CYBER["text"]), ("disabled", CYBER["muted"])],
            selectbackground=[("readonly", CYBER["cyan_dim"])],
            selectforeground=[("readonly", CYBER["text"])],
            arrowcolor=[("readonly", CYBER["cyan"]), ("active", CYBER["yellow"])],
        )

    def _build(self) -> None:
        header = tk.Frame(self.root, bg=CYBER["bg"])
        header.pack(fill="x", padx=24, pady=(18, 10))

        title_box = tk.Frame(header, bg=CYBER["bg"])
        title_box.pack(fill="x", expand=True)
        tk.Label(
            title_box,
            text="KyMoRem",
            fg=CYBER["cyan"],
            bg=CYBER["bg"],
            font=("Consolas", 34, "bold"),
        ).pack(anchor="w")
        tk.Label(
            title_box,
            text=f"by {APP_AUTHOR}",
            fg=CYBER["text"],
            bg=CYBER["bg"],
            font=("Consolas", 11, "bold"),
        ).pack(anchor="w", pady=(0, 2))
        tk.Label(
            title_box,
            text=f"{APP_EXTENDED_NAME} // {APP_SHORT_MARK} // RIGHT EDGE ROUTER // LAN NODE 54865",
            fg=CYBER["pink"],
            bg=CYBER["bg"],
            font=("Consolas", 11, "bold"),
        ).pack(anchor="w", pady=(0, 2))

        header_controls = tk.Frame(header, bg=CYBER["bg"])
        header_controls.pack(fill="x", pady=(8, 0))
        header_controls_inner = tk.Frame(header_controls, bg=CYBER["bg"])
        header_controls_inner.pack(side="right")

        self.mode_box = ThemedSelect(header_controls_inner, values=list(MODE_VALUES.keys()), width=8)
        self.mode_box.set(MODE_LABELS.get(str(self.config.get("mode", "client")), "Client"))
        self.mode_box.bind("<<ComboboxSelected>>", self._change_mode)
        self.mode_box.pack(side="left", padx=(0, 12))

        self.theme_box = ThemedSelect(header_controls_inner, values=list(THEME_VALUES.keys()), width=22)
        self.theme_box.set(THEME_LABELS.get(self.theme_id, THEME_LABELS["old_school_x11"]))
        self.theme_box.bind("<<ComboboxSelected>>", self._change_theme)
        self.theme_box.pack(side="left", padx=(0, 12))

        self.lang_box = ThemedSelect(header_controls_inner, values=list(LANG_VALUES.keys()), width=13)
        self.lang_box.set(LANG_LABELS.get(self.lang, LANG_LABELS["it"]))
        self.lang_box.bind("<<ComboboxSelected>>", self._change_lang)
        self.lang_box.pack(side="left")

        body = tk.PanedWindow(self.root, orient="horizontal", bg=CYBER["bg"], sashwidth=6, bd=0)
        body.pack(fill="both", expand=True, padx=24, pady=10)

        left = tk.Frame(body, bg=CYBER["bg"])
        right_shell = tk.Frame(body, bg=CYBER["bg"])
        body.add(left, minsize=480, stretch="always")
        body.add(right_shell, minsize=300)

        right_canvas = tk.Canvas(right_shell, bg=CYBER["panel"], highlightthickness=1, highlightbackground=CYBER["line"], width=340)
        right_scroll_y = tk.Scrollbar(right_shell, orient="vertical", command=right_canvas.yview)
        right_scroll_x = tk.Scrollbar(right_shell, orient="horizontal", command=right_canvas.xview)
        right_canvas.configure(yscrollcommand=right_scroll_y.set, xscrollcommand=right_scroll_x.set)
        right_canvas.grid(row=0, column=0, sticky="nsew")
        right_scroll_y.grid(row=0, column=1, sticky="ns")
        right_scroll_x.grid(row=1, column=0, sticky="ew")
        right_shell.columnconfigure(0, weight=1)
        right_shell.rowconfigure(0, weight=1)

        right = tk.Frame(right_canvas, bg=CYBER["panel"])
        right_window = right_canvas.create_window((0, 0), window=right, anchor="nw")

        def _sync_right_scrollbars() -> None:
            bbox = right_canvas.bbox("all") or (0, 0, 0, 0)
            content_w = bbox[2] - bbox[0]
            content_h = bbox[3] - bbox[1]
            view_w = max(1, right_canvas.winfo_width())
            view_h = max(1, right_canvas.winfo_height())
            if content_h > view_h + 2:
                right_scroll_y.grid(row=0, column=1, sticky="ns")
            else:
                right_scroll_y.grid_remove()
                right_canvas.yview_moveto(0)
            if content_w > view_w + 2:
                right_scroll_x.grid(row=1, column=0, sticky="ew")
            else:
                right_scroll_x.grid_remove()
                right_canvas.xview_moveto(0)

        def _right_configure(_event=None) -> None:
            right_canvas.configure(scrollregion=right_canvas.bbox("all"))
            self.root.after_idle(_sync_right_scrollbars)

        def _right_canvas_configure(event) -> None:
            right_canvas.itemconfigure(right_window, width=max(event.width, 340))
            right_canvas.configure(scrollregion=right_canvas.bbox("all"))
            self.root.after_idle(_sync_right_scrollbars)

        right.bind("<Configure>", _right_configure)
        right_canvas.bind("<Configure>", _right_canvas_configure)

        self.canvas = tk.Canvas(left, bg=CYBER["bg2"], highlightthickness=1, highlightbackground=CYBER["line"])
        self.canvas.pack(fill="both", expand=True)
        self.canvas.bind("<Configure>", lambda _event: self._draw_layout())
        self.canvas.bind("<Button-1>", self._canvas_press)
        self.canvas.bind("<B1-Motion>", self._canvas_drag)
        self.canvas.bind("<ButtonRelease-1>", self._canvas_release)

        controls_shell = tk.Frame(left, bg=CYBER["bg"])
        controls_shell.pack(fill="x", pady=(14, 0))
        controls_canvas = tk.Canvas(controls_shell, bg=CYBER["bg"], highlightthickness=0, height=58)
        controls_scroll = tk.Scrollbar(controls_shell, orient="horizontal", command=controls_canvas.xview)
        controls_canvas.configure(xscrollcommand=controls_scroll.set)
        controls_canvas.pack(fill="x", expand=True)
        controls_scroll.pack(fill="x")
        controls = tk.Frame(controls_canvas, bg=CYBER["bg"])
        controls_window = controls_canvas.create_window((0, 0), window=controls, anchor="nw")

        def _sync_controls_scrollbar() -> None:
            bbox = controls_canvas.bbox("all") or (0, 0, 0, 0)
            content_w = bbox[2] - bbox[0]
            view_w = max(1, controls_canvas.winfo_width())
            if content_w > view_w + 2:
                if not controls_scroll.winfo_ismapped():
                    controls_scroll.pack(fill="x")
            else:
                if controls_scroll.winfo_ismapped():
                    controls_scroll.pack_forget()
                controls_canvas.xview_moveto(0)

        def _controls_configure(_event=None) -> None:
            controls_canvas.configure(scrollregion=controls_canvas.bbox("all"))
            self.root.after_idle(_sync_controls_scrollbar)

        controls.bind("<Configure>", _controls_configure)
        controls_canvas.bind(
            "<Configure>",
            lambda event: (
                controls_canvas.itemconfigure(controls_window, height=event.height),
                controls_canvas.configure(scrollregion=controls_canvas.bbox("all")),
                self.root.after_idle(_sync_controls_scrollbar),
            ),
        )
        self.server_toggle = self._neon_button(controls, "", self._toggle_server, CYBER["acid"])
        self.server_toggle.pack(side="left", padx=(0, 8))
        self._neon_button(controls, self.text["connect"], self._connect, CYBER["cyan"]).pack(side="left", padx=(0, 8))
        self._neon_button(controls, self.text["disconnect"], self.link.disconnect, CYBER["pink"]).pack(side="left", padx=8)
        self._neon_button(controls, self.text["take"], self.engine.take, CYBER["acid"]).pack(side="left", padx=8)
        self._neon_button(controls, self.text["release"], self.engine.release, CYBER["yellow"]).pack(side="left", padx=8)
        self._neon_button(controls, self.text["test"], lambda: self.link.send("pulse"), CYBER["cyan"]).pack(side="left", padx=8)

        tk.Label(right, text="NODE STATUS", fg=CYBER["pink"], bg=CYBER["panel"], font=("Consolas", 15, "bold")).pack(anchor="w", padx=18, pady=(18, 4))
        self.status = tk.Label(
            right,
            text="BOOT // READY",
            fg=CYBER["acid"],
            bg=CYBER["panel2"],
            font=("Consolas", 12, "bold"),
            padx=12,
            pady=8,
        )
        self.status.pack(fill="x", padx=16, pady=(0, 14))

        self.client_badge = tk.Label(
            right,
            text=f"RIGHT NODE // {self._client_host()}",
            fg=CYBER["cyan"],
            bg=CYBER["panel"],
            font=("Consolas", 10, "bold"),
        )
        self.client_badge.pack(anchor="w", padx=18, pady=(0, 12))

        self.discovery_badge = tk.Label(
            right,
            text="DISCOVERY // OFF" if not self.server_active else "DISCOVERY // ARMED",
            fg=CYBER["muted"],
            bg=CYBER["panel"],
            font=("Consolas", 9, "bold"),
        )
        self.discovery_badge.pack(anchor="w", padx=18, pady=(0, 12))

        self.signature_badge = tk.Label(
            right,
            text=f"{APP_SIGNATURE} // {VERSION}",
            fg=CYBER["yellow"],
            bg=CYBER["panel"],
            font=("Consolas", 9, "bold"),
            wraplength=320,
            justify="left",
        )
        self.signature_badge.pack(anchor="w", padx=18, pady=(0, 12))

        tk.Label(right, text="CLIENT MAP", fg=CYBER["cyan"], bg=CYBER["panel"], font=("Consolas", 12, "bold")).pack(anchor="w", padx=18, pady=(0, 6))
        self.client_list = tk.Listbox(
            right,
            height=7,
            bg=CYBER["panel2"],
            fg=CYBER["text"],
            selectbackground=CYBER["cyan_dim"],
            selectforeground=CYBER["text"],
            highlightthickness=1,
            highlightbackground=CYBER["line"],
            relief="flat",
            font=("Consolas", 9),
        )
        self.client_list.pack(fill="x", padx=16, pady=(0, 10))
        self.client_list.bind("<<ListboxSelect>>", self._select_client_from_list)

        form = tk.Frame(right, bg=CYBER["panel"])
        form.pack(fill="x", padx=16, pady=(0, 10))
        self.client_name_var = tk.StringVar()
        self.client_host_var = tk.StringVar()
        self.client_port_var = tk.StringVar(value=str(PORT))
        self.client_position_var = tk.StringVar(value="right")
        self._field(form, "NOME", self.client_name_var, 0)
        self._field(form, "IP", self.client_host_var, 1)
        self._field(form, "PORTA", self.client_port_var, 2)
        tk.Label(form, text="POS", fg=CYBER["muted"], bg=CYBER["panel"], font=("Consolas", 8, "bold")).grid(row=3, column=0, sticky="w", pady=2)
        self.position_box = ThemedSelect(
            form,
            values=["right", "left", "up", "down"],
            width=16,
            textvariable=self.client_position_var,
        )
        self.position_box.grid(row=3, column=1, sticky="ew", pady=2)
        form.columnconfigure(1, weight=1)

        client_buttons = tk.Frame(right, bg=CYBER["panel"])
        client_buttons.pack(fill="x", padx=16, pady=(0, 10))
        self._mini_button(client_buttons, "ADD", self._add_manual_client, CYBER["acid"]).grid(row=0, column=0, padx=2, pady=2, sticky="ew")
        self._mini_button(client_buttons, "SAVE", self._save_selected_client, CYBER["cyan"]).grid(row=0, column=1, padx=2, pady=2, sticky="ew")
        self._mini_button(client_buttons, "DEL", self._delete_selected_client, CYBER["red"]).grid(row=0, column=2, padx=2, pady=2, sticky="ew")
        self._mini_button(client_buttons, "USE", self._connect, CYBER["yellow"]).grid(row=0, column=3, padx=2, pady=2, sticky="ew")
        for col in range(4):
            client_buttons.columnconfigure(col, weight=1)

        move_pad = tk.Frame(right, bg=CYBER["panel"])
        move_pad.pack(fill="x", padx=16, pady=(0, 12))
        self._mini_button(move_pad, "UP", lambda: self._move_selected(0, -1), CYBER["cyan"]).grid(row=0, column=1, padx=2, pady=2, sticky="ew")
        self._mini_button(move_pad, "LEFT", lambda: self._move_selected(-1, 0), CYBER["cyan"]).grid(row=1, column=0, padx=2, pady=2, sticky="ew")
        self._mini_button(move_pad, "RIGHT", lambda: self._move_selected(1, 0), CYBER["cyan"]).grid(row=1, column=2, padx=2, pady=2, sticky="ew")
        self._mini_button(move_pad, "DOWN", lambda: self._move_selected(0, 1), CYBER["cyan"]).grid(row=2, column=1, padx=2, pady=2, sticky="ew")
        for col in range(3):
            move_pad.columnconfigure(col, weight=1)

        tk.Label(right, text="CLIPBOARD", fg=CYBER["cyan"], bg=CYBER["panel"], font=("Consolas", 12, "bold")).pack(anchor="w", padx=18, pady=(0, 6))
        clip = self.config.setdefault("clipboard", {})
        self.clipboard_enabled_var = tk.BooleanVar(value=bool(clip.get("enabled", False)))
        self.clipboard_files_var = tk.BooleanVar(value=bool(clip.get("files_enabled", False)))
        checks = tk.Frame(right, bg=CYBER["panel"])
        checks.pack(fill="x", padx=16, pady=(0, 8))
        self._check(checks, "TEXT", self.clipboard_enabled_var, self._save_clipboard_config).pack(side="left", padx=(0, 8))
        self._check(checks, "FILES", self.clipboard_files_var, self._save_clipboard_config).pack(side="left")
        clip_buttons = tk.Frame(right, bg=CYBER["panel"])
        clip_buttons.pack(fill="x", padx=16, pady=(0, 12))
        self._mini_button(clip_buttons, "SEND TEXT", self._send_clipboard_text, CYBER["acid"]).grid(row=0, column=0, padx=2, pady=2, sticky="ew")
        self._mini_button(clip_buttons, "GET TEXT", self._request_clipboard_text, CYBER["cyan"]).grid(row=0, column=1, padx=2, pady=2, sticky="ew")
        self._mini_button(clip_buttons, "SEND FILES", self._send_clipboard_files, CYBER["yellow"]).grid(row=0, column=2, padx=2, pady=2, sticky="ew")
        for col in range(3):
            clip_buttons.columnconfigure(col, weight=1)

        tk.Label(right, text="EVENT STREAM", fg=CYBER["yellow"], bg=CYBER["panel"], font=("Consolas", 12, "bold")).pack(anchor="w", padx=18, pady=(6, 8))
        self.log = tk.Text(
            right,
            width=38,
            height=18,
            bg=CYBER["panel2"],
            fg=CYBER["text"],
            insertbackground=CYBER["cyan"],
            relief="flat",
            font=("Consolas", 9),
            borderwidth=0,
        )
        self.log.pack(fill="both", expand=True, padx=16, pady=(0, 16))
        self._refresh_server_toggle()

        tk.Label(
            self.root,
            text="CONTROL VECTOR: RIGHT EDGE // RELEASE: Ctrl+Esc // FIND POINTER: Ctrl+Shift+M",
            fg=CYBER["muted"],
            bg=CYBER["bg"],
            font=("Consolas", 9),
        ).pack(anchor="w", padx=24, pady=(0, 16))
        self._refresh_client_list()
        self._draw_layout()

    def _client_config(self) -> dict:
        clients = self.config.setdefault("clients", [])
        if not clients:
            clients.append(normalize_client(DEFAULT_CONFIG["clients"][0]))
        for client in clients:
            if client_key(client) == self.selected_client:
                return client
        self.selected_client = client_key(clients[0])
        return clients[0]

    def _client_by_key(self, key: str) -> dict | None:
        return next((client for client in self.config.get("clients", []) if client_key(client) == key), None)

    def _save_config(self) -> None:
        self.config["clients"] = [normalize_client(item, index) for index, item in enumerate(self.config.get("clients", []))]
        (app_dir() / "config.json").write_text(json.dumps(self.config, indent=2), encoding="utf-8")

    def _client_host(self) -> str:
        return str(self._client_config().get("host", "127.0.0.1"))

    def _client_port(self) -> int:
        return int(self._client_config().get("port", PORT))

    def _client_name(self) -> str:
        return str(self._client_config().get("name", "right-side-linux"))

    def _client_direction(self, client: dict | None = None) -> str:
        item = client or self._client_config()
        return position_from_grid(int(item.get("x", 1)), int(item.get("y", 0)))

    def _token(self) -> str:
        return str(self.config.get("token") or DEFAULT_CONFIG["token"])

    def _token_valid(self) -> bool:
        try:
            validate_token(self._token())
            return True
        except CryptoError as exc:
            self.status.configure(text="TOKEN REQUIRED", fg=CYBER["yellow"])
            self._log(f"Token non valido: {exc}")
            return False

    def _identity(self) -> dict:
        return {
            "role": "host",
            "name": self.config.get("server_name") or os.environ.get("COMPUTERNAME", "Windows"),
            "platform": "windows",
            "version": VERSION,
            "host": self.local_ip,
            "port": PORT,
        }

    def _discovery_enabled(self) -> bool:
        return bool(self.config.get("discovery", {}).get("enabled", True))

    def _discovery_auto_connect(self) -> bool:
        return bool(self.config.get("discovery", {}).get("auto_connect", True))

    def _relay_event(self, event: str, subject: str, body: str) -> None:
        relay = self.config.get("email_relay", {})
        if not relay.get("enabled"):
            return
        if event not in relay.get("events", []):
            return
        host = relay.get("smtp_host")
        recipients = relay.get("to", [])
        sender = relay.get("from")
        if not host or not recipients or not sender:
            self._log("Email relay non configurato: smtp_host/from/to mancanti.")
            return
        threading.Thread(target=self._send_relay_email, args=(relay, subject, body), daemon=True).start()

    def _send_relay_email(self, relay: dict, subject: str, body: str) -> None:
        message = EmailMessage()
        sender = self._safe_email(str(relay.get("from", "")))
        recipients = [self._safe_email(str(item)) for item in relay.get("to", [])]
        recipients = [item for item in recipients if item]
        if not sender or not recipients:
            self.events.put(("log", "Email relay fallito: mittente o destinatari non validi."))
            return
        message["From"] = sender
        message["To"] = ", ".join(recipients)
        message["Subject"] = self._safe_header(subject)
        message.set_content(body + f"\n\nHost: {self.local_ip}\nVersion: {VERSION}\n")
        password = os.environ.get(str(relay.get("smtp_password_env", "KYMOREM_SMTP_PASSWORD")), "")
        try:
            with smtplib.SMTP(str(relay.get("smtp_host")), int(relay.get("smtp_port", 587)), timeout=10) as smtp:
                if relay.get("smtp_starttls", True):
                    smtp.starttls(context=ssl.create_default_context())
                username = str(relay.get("smtp_username", ""))
                if username:
                    if not password:
                        raise RuntimeError("SMTP username configured but password env is empty")
                    smtp.login(username, password)
                smtp.send_message(message)
        except Exception as exc:
            self.events.put(("log", f"Email relay fallito: {exc}"))

    def _safe_header(self, value: str) -> str:
        return str(value).replace("\r", " ").replace("\n", " ")[:160]

    def _safe_email(self, value: str) -> str:
        if "\r" in value or "\n" in value:
            return ""
        _name, addr = parseaddr(value)
        if "@" not in addr:
            return ""
        return addr

    def _start_discovery(self) -> None:
        if not self.server_active:
            self.discovery_badge.configure(text="DISCOVERY // OFF")
            return
        if self.discovery_beacon or self.discovery_listener:
            return
        if not self._discovery_enabled():
            self._log("Discovery LAN disattivata da configurazione.")
            self.discovery_badge.configure(text="DISCOVERY // DISABLED")
            return
        token = self._token()
        try:
            validate_token(token)
        except CryptoError as exc:
            self._log(f"Discovery non avviata: {exc}")
            self.discovery_badge.configure(text="DISCOVERY // TOKEN REQUIRED")
            return
        name = str(self.config.get("server_name") or os.environ.get("COMPUTERNAME", "Windows"))
        self.discovery_beacon = DiscoveryBeacon(token, "host", name, PORT)
        self.discovery_listener = DiscoveryListener(token, lambda payload, addr: self.events.put(("discovery", (payload, addr))))
        self.discovery_beacon.start()
        self.discovery_listener.start()
        self._log("Discovery LAN cifrata attiva su UDP 54866.")

    def _stop_discovery(self) -> None:
        for service in (self.discovery_beacon, self.discovery_listener):
            if service:
                try:
                    service.close()
                except Exception:
                    pass
        self.discovery_beacon = None
        self.discovery_listener = None
        if hasattr(self, "discovery_badge"):
            try:
                self.discovery_badge.configure(text="DISCOVERY // OFF")
            except tk.TclError:
                pass

    def _handle_discovery(self, event) -> None:
        if not self.server_active:
            return
        message, addr = event
        if message.get("type") != "discovery_announce":
            return
        payload = message.get("payload", {})
        if payload.get("role") != "client":
            return
        host = str(payload.get("host") or addr[0])
        if host in {"127.0.0.1", "localhost"}:
            host = addr[0]
        port = int(payload.get("port", PORT))
        name = str(payload.get("name") or host)
        self.discovered_clients[name] = {"host": host, "port": port, "name": name, "seen": time.time()}
        self.discovery_badge.configure(text=f"DISCOVERY // {len(self.discovered_clients)} CLIENT")
        clients = self.config.setdefault("clients", [])
        key = f"{host}:{port}"
        existing = next((client for client in clients if client_key(client) == key), None)
        if existing:
            existing["name"] = name
            existing["source"] = existing.get("source", "discovery")
        elif len(clients) < MAX_CLIENTS:
            gx, gy = next_free_position(clients)
            clients.append(normalize_client({"name": name, "host": host, "port": port, "x": gx, "y": gy, "source": "discovery"}))
            self._log(f"Client scoperto: {name} {host}:{port}")
        self._save_config()
        self._refresh_client_list()
        self._draw_layout()
        if self._discovery_auto_connect() and not self.link.connected and not self.link.connecting:
            target = self._client_by_key(key)
            if target:
                self.selected_client = client_key(target)
                self._connect()

    def _neon_button(self, parent, text: str, command, accent: str) -> tk.Button:
        return tk.Button(
            parent,
            text=text.upper(),
            command=command,
            bg=CYBER["panel2"],
            fg=accent,
            activebackground=accent,
            activeforeground=CYBER["bg"],
            highlightbackground=accent,
            highlightcolor=accent,
            highlightthickness=1,
            bd=0,
            padx=14,
            pady=9,
            font=("Consolas", 9, "bold"),
            cursor="hand2",
        )

    def _mini_button(self, parent, text: str, command, accent: str) -> tk.Button:
        return tk.Button(
            parent,
            text=text,
            command=command,
            bg=CYBER["panel2"],
            fg=accent,
            activebackground=accent,
            activeforeground=CYBER["bg"],
            bd=0,
            padx=8,
            pady=5,
            font=("Consolas", 8, "bold"),
            cursor="hand2",
        )

    def _field(self, parent, label: str, variable: tk.StringVar, row: int) -> None:
        tk.Label(parent, text=label, fg=CYBER["muted"], bg=CYBER["panel"], font=("Consolas", 8, "bold")).grid(row=row, column=0, sticky="w", pady=2)
        entry = tk.Entry(parent, textvariable=variable, bg=CYBER["panel2"], fg=CYBER["text"], insertbackground=CYBER["cyan"], relief="flat", font=("Consolas", 9))
        entry.grid(row=row, column=1, sticky="ew", pady=2)

    def _check(self, parent, text: str, variable: tk.BooleanVar, command) -> tk.Checkbutton:
        return tk.Checkbutton(
            parent,
            text=text,
            variable=variable,
            command=command,
            bg=CYBER["panel"],
            fg=CYBER["text"],
            activebackground=CYBER["panel"],
            activeforeground=CYBER["cyan"],
            selectcolor=CYBER["panel2"],
            font=("Consolas", 8, "bold"),
        )

    def _refresh_client_list(self) -> None:
        if not hasattr(self, "client_list"):
            return
        self.client_list.delete(0, "end")
        selected_index = 0
        for index, client in enumerate(self.config.get("clients", [])):
            key = client_key(client)
            marker = "*" if key == self.selected_client else " "
            source = str(client.get("source", "manual"))[:3].upper()
            self.client_list.insert(
                "end",
                f"{marker} {client.get('name')} {client.get('host')}:{client.get('port')} [{client.get('x')},{client.get('y')}] {source}",
            )
            if key == self.selected_client:
                selected_index = index
        if self.config.get("clients"):
            self.client_list.selection_clear(0, "end")
            self.client_list.selection_set(selected_index)
            self.client_list.activate(selected_index)
            self._load_client_form(self._client_config())

    def _load_client_form(self, client: dict) -> None:
        self.client_name_var.set(str(client.get("name", "")))
        self.client_host_var.set(str(client.get("host", "")))
        self.client_port_var.set(str(client.get("port", PORT)))
        self.client_position_var.set(self._client_direction(client))

    def _select_client_from_list(self, _event=None) -> None:
        selection = self.client_list.curselection()
        if not selection:
            return
        index = int(selection[0])
        clients = self.config.get("clients", [])
        if index >= len(clients):
            return
        self.selected_client = client_key(clients[index])
        self._load_client_form(clients[index])
        self.client_badge.configure(text=f"{self._client_direction(clients[index]).upper()} NODE // {clients[index].get('host')}")
        self._refresh_client_list()
        self._draw_layout()

    def _manual_form_client(self) -> dict | None:
        name = self.client_name_var.get().strip() or f"client-{len(self.config.get('clients', [])) + 1}"
        host = self.client_host_var.get().strip()
        if not host:
            messagebox.showwarning(APP_NAME, "IP/host richiesto.")
            return None
        try:
            port = int(self.client_port_var.get().strip() or PORT)
        except ValueError:
            messagebox.showwarning(APP_NAME, "Porta non valida.")
            return None
        gx, gy = grid_from_position(self.client_position_var.get())
        return normalize_client({"name": name, "host": host, "port": port, "x": gx, "y": gy, "source": "manual", "enabled": True})

    def _add_manual_client(self) -> None:
        client = self._manual_form_client()
        if not client:
            return
        clients = self.config.setdefault("clients", [])
        existing = next((item for item in clients if client_key(item) == client_key(client)), None)
        if existing:
            existing.update(client)
        else:
            clients.append(client)
        self.selected_client = client_key(client)
        self._save_config()
        self._refresh_client_list()
        self._draw_layout()
        self._log(f"Client manuale salvato: {client.get('name')} {client.get('host')}:{client.get('port')}")

    def _save_selected_client(self) -> None:
        selected = self._client_config()
        form = self._manual_form_client()
        if not form:
            return
        selected.update(form)
        self.selected_client = client_key(selected)
        self._save_config()
        self._refresh_client_list()
        self._draw_layout()
        self._log(f"Client aggiornato: {selected.get('name')}")

    def _delete_selected_client(self) -> None:
        clients = self.config.get("clients", [])
        if len(clients) <= 1:
            messagebox.showwarning(APP_NAME, "Mantieni almeno un client configurato.")
            return
        self.config["clients"] = [item for item in clients if client_key(item) != self.selected_client]
        self.selected_client = client_key(self.config["clients"][0])
        self._save_config()
        self._refresh_client_list()
        self._draw_layout()

    def _move_selected(self, dx: int, dy: int) -> None:
        client = self._client_config()
        client["x"] = max(-4, min(4, int(client.get("x", 1)) + dx))
        client["y"] = max(-4, min(4, int(client.get("y", 0)) + dy))
        if client["x"] == 0 and client["y"] == 0:
            client["x"] = dx or 1
            client["y"] = dy
        client["position"] = position_from_grid(client["x"], client["y"])
        self._save_config()
        self._refresh_client_list()
        self._draw_layout()

    def _save_clipboard_config(self) -> None:
        clip = self.config.setdefault("clipboard", {})
        clip["enabled"] = bool(self.clipboard_enabled_var.get())
        clip["files_enabled"] = bool(self.clipboard_files_var.get())
        clip["text_only"] = not bool(self.clipboard_files_var.get())
        self._save_config()
        self._log(f"Clipboard text={'on' if clip['enabled'] else 'off'} files={'on' if clip['files_enabled'] else 'off'}")

    def _clipboard_config(self) -> dict:
        merged = dict(DEFAULT_CONFIG["clipboard"])
        merged.update(self.config.get("clipboard", {}))
        return merged

    def _local_clipboard_text(self) -> str:
        try:
            return self.root.clipboard_get()
        except tk.TclError:
            return ""

    def _set_local_clipboard_text(self, text: str) -> None:
        self.root.clipboard_clear()
        self.root.clipboard_append(text)
        self.root.update_idletasks()

    def _send_clipboard_text(self) -> None:
        clip = self._clipboard_config()
        if not clip.get("enabled"):
            self._log("Clipboard testo disattivato.")
            return
        if not self.link.connected:
            self._log("Clipboard non inviato: nessun client connesso.")
            return
        text = self._local_clipboard_text()
        size = len(text.encode("utf-8"))
        if not text:
            self._log("Clipboard locale vuoto o non testuale.")
            return
        if size > int(clip.get("max_bytes", 1048576)):
            self._log(f"Clipboard troppo grande: {size} byte.")
            return
        self.link.send("clipboard_text", text=text)
        self._log(f"Clipboard testo inviato: {size} byte.")

    def _request_clipboard_text(self) -> None:
        if not self._clipboard_config().get("enabled"):
            self._log("Clipboard testo disattivato.")
            return
        if not self.link.connected:
            self._log("Richiesta clipboard non inviata: nessun client connesso.")
            return
        self.link.send("clipboard_request", files=bool(self._clipboard_config().get("files_enabled")))
        self._log("Richiesta clipboard testo inviata al client.")

    def _send_clipboard_files(self) -> None:
        clip = self._clipboard_config()
        if not clip.get("files_enabled"):
            self._log("Clipboard file disattivato.")
            return
        if not self.link.connected:
            self._log("File non inviati: nessun client connesso.")
            return
        paths = windows_clipboard_files()
        if not paths:
            selected = filedialog.askopenfilenames(title="Scegli file da inviare al client")
            paths = [Path(path) for path in selected]
        paths = [path for path in paths if path.is_file()]
        if not paths:
            self._log("Nessun file valido da inviare.")
            return
        threading.Thread(target=self._send_files_thread, args=(paths,), daemon=True).start()

    def _send_files_thread(self, paths: list[Path]) -> None:
        clip = self._clipboard_config()
        max_file = int(clip.get("max_file_bytes", 5 * 1024 * 1024))
        chunk_size = max(4096, min(32768, int(clip.get("chunk_bytes", 32768))))
        for path in paths:
            try:
                size = path.stat().st_size
                if size > max_file:
                    self.events.put(("log", f"File saltato, troppo grande: {path.name} ({size} byte)"))
                    continue
                transfer_id = uuid.uuid4().hex
                self.link.send("file_begin", transfer_id=transfer_id, name=path.name, size=size)
                with path.open("rb") as handle:
                    while True:
                        chunk = handle.read(chunk_size)
                        if not chunk:
                            break
                        self.link.send("file_chunk", transfer_id=transfer_id, data=base64.b64encode(chunk).decode("ascii"))
                self.link.send("file_end", transfer_id=transfer_id)
                self.events.put(("log", f"File inviato: {path.name} ({size} byte)"))
            except Exception as exc:
                self.events.put(("log", f"Invio file fallito {path.name}: {exc}"))

    def _route_from_edge(self, direction: str, entry: dict | None = None) -> bool:
        if not self.server_active:
            self.events.put(("log", "Server OFF: routing bordo disattivato."))
            return False
        candidates = [
            client
            for client in self.config.get("clients", [])
            if client.get("enabled", True) and self._client_direction(client) == direction
        ]
        if not candidates:
            self.events.put(("log", f"Nessun client assegnato al bordo {direction}."))
            return False
        target = sorted(candidates, key=lambda item: abs(int(item.get("x", 0))) + abs(int(item.get("y", 0))))[0]
        self.selected_client = client_key(target)
        self.events.put(("select", self.selected_client))
        endpoint = (str(target.get("host")), int(target.get("port", PORT)))
        if self.link.connected and self.link.endpoint == endpoint:
            return True
        self.pending_take_direction = direction
        self.pending_take_entry = entry
        if not self.link.connecting:
            self.link.connect(endpoint[0], endpoint[1], self._token(), self._identity())
        return False

    def _change_theme(self, _event=None) -> None:
        self.theme_id = THEME_VALUES.get(self.theme_box.get(), "old_school_x11")
        self.config["theme"] = self.theme_id
        CYBER.update(THEMES.get(self.theme_id, THEMES["old_school_x11"]))
        self._save_config()
        for child in self.root.winfo_children():
            child.destroy()
        self.root.configure(bg=CYBER["bg"])
        self._style()
        self._build()
        self._log(f"Tema impostato: {self.theme_id}. UI aggiornata.")
        self._draw_layout()

    def _change_mode(self, _event=None) -> None:
        mode = MODE_VALUES.get(self.mode_box.get(), "client")
        if mode not in {"server", "client"}:
            mode = "client"
        self.config["mode"] = mode
        if mode == "client":
            self._set_server_active(False)
            self._log("Modalita client salvata. Server e discovery spenti.")
            return
        self._save_config()
        self._log("Modalita server salvata. Usa SERVER ON per attivare connessione, discovery e routing.")

    def _toggle_server(self) -> None:
        self._set_server_active(not self.server_active)

    def _refresh_server_toggle(self) -> None:
        if not hasattr(self, "server_toggle"):
            return
        if self.server_active:
            self.server_toggle.configure(
                text="SERVER OFF",
                fg=CYBER["red"],
                activebackground=CYBER["red"],
                highlightbackground=CYBER["red"],
                highlightcolor=CYBER["red"],
            )
            self.status.configure(text="SERVER ON", fg=CYBER["acid"])
        else:
            self.server_toggle.configure(
                text="SERVER ON",
                fg=CYBER["acid"],
                activebackground=CYBER["acid"],
                highlightbackground=CYBER["acid"],
                highlightcolor=CYBER["acid"],
            )
            if not self.link.connected:
                self.status.configure(text="CLIENT MODE", fg=CYBER["yellow"])

    def _set_server_active(self, active: bool) -> None:
        if active:
            self.config["mode"] = "server"
            self.config["server_on"] = True
            if hasattr(self, "mode_box"):
                self.mode_box.set(MODE_LABELS["server"])
            if not self._token_valid():
                self.config["server_on"] = False
                self.server_active = False
                self.engine.enabled = False
                self._save_config()
                self._refresh_server_toggle()
                return
            self.server_active = True
            self.engine.enabled = True
            self._save_config()
            self._refresh_server_toggle()
            self._start_discovery()
            self._auto_connect()
            self._log("Server ON: discovery, connessione client e routing bordo attivi.")
            return

        if self.engine.remote:
            self.engine.release()
        self.pending_take_direction = None
        self.pending_take_entry = None
        self.server_active = False
        self.engine.enabled = False
        self.config["server_on"] = False
        if hasattr(self, "mode_box") and self.config.get("mode") not in {"server", "client"}:
            self.mode_box.set(MODE_LABELS["client"])
        self.link.disconnect()
        self._stop_discovery()
        self._save_config()
        self._refresh_server_toggle()

    def _point_to_grid(self, x: int, y: int) -> tuple[int, int]:
        w = max(420, self.canvas.winfo_width())
        h = max(320, self.canvas.winfo_height())
        center_x = w // 2
        center_y = h // 2
        cell_w = max(150, min(210, w // 5))
        cell_h = max(105, min(145, h // 4))
        gx = round((x - center_x) / cell_w)
        gy = round((y - center_y) / cell_h)
        gx = max(-4, min(4, gx))
        gy = max(-4, min(4, gy))
        if gx == 0 and gy == 0:
            gx = 1
        return gx, gy

    def _canvas_press(self, event) -> None:
        for key, box in self.client_boxes.items():
            x1, y1, x2, y2 = box
            if x1 <= event.x <= x2 and y1 <= event.y <= y2:
                self.selected_client = key
                self.drag_client = key
                self._refresh_client_list()
                self._draw_layout()
                return

    def _canvas_drag(self, event) -> None:
        if not self.drag_client:
            return
        client = self._client_by_key(self.drag_client)
        if not client:
            return
        client["x"], client["y"] = self._point_to_grid(event.x, event.y)
        client["position"] = position_from_grid(client["x"], client["y"])
        self._draw_layout()

    def _canvas_release(self, _event) -> None:
        if self.drag_client:
            self._save_config()
            self._refresh_client_list()
            self.drag_client = None
            self._draw_layout()

    def _start_tray(self) -> None:
        if pystray is None or Image is None:
            self._log("Tray non disponibile: pystray/Pillow mancanti.")
            return
        icon_file = asset_path("kymorem-64.png")
        if not icon_file.exists():
            icon_file = asset_path("kymorem.ico")
        if not icon_file.exists():
            self._log("Tray non disponibile: icona mancante.")
            return

        image = Image.open(icon_file)
        menu = pystray.Menu(
            pystray.MenuItem("Apri KyMoRem", lambda _icon, _item: self.root.after(0, self._show_window)),
            pystray.MenuItem("Server ON/OFF", lambda _icon, _item: self.root.after(0, self._toggle_server)),
            pystray.MenuItem("Connetti client", lambda _icon, _item: self.root.after(0, self._connect)),
            pystray.MenuItem("Prendi controllo", lambda _icon, _item: self.root.after(0, self.engine.take)),
            pystray.MenuItem("Rilascia", lambda _icon, _item: self.root.after(0, self.engine.release)),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Esci", lambda _icon, _item: self.root.after(0, self._quit)),
        )
        self.tray_icon = pystray.Icon(
            "KyMoRem",
            image,
            "KyMoRem // Right Edge Router",
            menu,
        )
        self.tray_icon.run_detached()
        self._log("Tray Windows attiva.")

    def _hide_to_tray(self) -> None:
        if self.tray_icon:
            self.root.withdraw()
            self._log("KyMoRem nascosto in tray.")
        else:
            self._quit()

    def _show_window(self) -> None:
        self.root.deiconify()
        self.root.lift()
        self.root.focus_force()

    def _quit(self) -> None:
        self.engine.stop()
        self._stop_discovery()
        self.link.disconnect()
        if self.tray_icon:
            try:
                self.tray_icon.stop()
            except Exception:
                pass
            self.tray_icon = None
        self.root.destroy()

    def _draw_layout(self) -> None:
        c = self.canvas
        c.delete("all")
        w = max(420, c.winfo_width())
        h = max(320, c.winfo_height())
        c.create_rectangle(0, 0, w, h, fill=CYBER["bg2"], outline="")
        self._draw_cyber_grid(w, h)

        self.client_boxes = {}
        center_x = w // 2
        center_y = h // 2
        gap = 40
        cell_w = max(210, min(260, w // 4))
        cell_h = max(145, min(175, h // 3))
        node_w = 220
        node_h = 118
        clients = self.config.get("clients", [])
        if clients and any(int(client.get("x", 0)) > 0 for client in clients) and not any(int(client.get("x", 0)) < 0 for client in clients):
            cell_w = max(cell_w, node_w + gap)
            center_x = max(node_w // 2 + 24, min(w - node_w // 2 - 24, w // 2 - (node_w + gap) // 2))
        elif clients and any(int(client.get("x", 0)) < 0 for client in clients) and not any(int(client.get("x", 0)) > 0 for client in clients):
            cell_w = max(cell_w, node_w + gap)
            center_x = max(node_w // 2 + 24, min(w - node_w // 2 - 24, w // 2 + (node_w + gap) // 2))
        server = (center_x - node_w // 2, center_y - node_h // 2, center_x + node_w // 2, center_y + node_h // 2)
        server_state = "SERVER ON" if self.server_active else "CLIENT MODE"
        self._node_card(server, "SERVER", server_state, CYBER["cyan"], active=self.server_active and not self.engine.remote)
        self._portal(center_x, center_y, CYBER["cyan"])

        selected = self._client_config()
        selected_key = client_key(selected)
        link_color = CYBER["acid"] if self.link.connected else CYBER["line"]
        for client in clients:
            gx = int(client.get("x", 1))
            gy = int(client.get("y", 0))
            cx = max(node_w // 2 + 18, min(w - node_w // 2 - 18, center_x + gx * cell_w))
            cy = max(node_h // 2 + 18, min(h - node_h // 2 - 18, center_y + gy * cell_h))
            box = (cx - node_w // 2, cy - node_h // 2, cx + node_w // 2, cy + node_h // 2)
            key = client_key(client)
            self.client_boxes[key] = box
            active = self.link.connected and self.link.endpoint == (str(client.get("host")), int(client.get("port", PORT)))
            color = CYBER["pink"] if key == selected_key else CYBER["cyan"]
            if active:
                color = CYBER["acid"]
            c.create_line(center_x, center_y, cx, cy, fill=CYBER["cyan_dim"] if active else CYBER["line"], width=2)
            self._node_card(
                box,
                str(client.get("name", "client")).upper()[:18],
                f"{client.get('host')}:{client.get('port')} // {client.get('position')}",
                color,
                active=active,
            )

        if not self.server_active:
            route_text = "CLIENT MODE // SERVER OFF"
        else:
            route_text = "LINK ONLINE // EDGE ROUTING ARMED" if self.link.connected else "LINK OFFLINE // SELECT OR DISCOVER NODE"
        if self.engine.remote:
            route_text = "REMOTE CONTROL ACTIVE // RETURN VIA LEFT EDGE"
        c.create_text(w // 2, max(28, center_y + node_h // 2 + 42), text=route_text, fill=link_color if self.link.connected else CYBER["muted"], font=("Consolas", 13, "bold"))
        if self.pointer_hint and time.monotonic() < self.pointer_hint_until:
            hint = self.pointer_hint
            label = (
                f"POINTER // {hint.get('scope', 'server').upper()} "
                f"X={hint.get('x')} Y={hint.get('y')} // {hint.get('screen', '')}"
            )
            c.create_rectangle(28, h - 82, min(w - 28, 610), h - 50, fill=CYBER["panel"], outline=CYBER["yellow"], width=1)
            c.create_text(44, h - 66, text=label, anchor="w", fill=CYBER["yellow"], font=("Consolas", 11, "bold"))
        c.create_text(
            w // 2,
            h - 28,
            text=f"{self.local_ip}  >>>  {self._client_host()}:{self._client_port()} // selected {self._client_direction()}",
            fill=CYBER["muted"],
            font=("Consolas", 10),
        )

    def _draw_cyber_grid(self, w: int, h: int) -> None:
        c = self.canvas
        c.create_rectangle(18, 18, w - 18, h - 18, outline=CYBER["line"], width=1)
        c.create_text(w - 28, 32, text="Client Layout", anchor="e", fill=CYBER["muted"], font=("Consolas", 10, "bold"))
        c.create_text(28, 32, text=f"{APP_SHORT_MARK} Routing Map", anchor="w", fill=CYBER["muted"], font=("Consolas", 10, "bold"))

    def _beveled_rect(self, box: tuple[int, int, int, int], outline: str, fill: str) -> None:
        x1, y1, x2, y2 = box
        self.canvas.create_rectangle(x1, y1, x2, y2, fill=fill, outline=outline, width=2)

    def _node_card(self, box: tuple[int, int, int, int], title: str, subtitle: str, color: str, active: bool) -> None:
        x1, y1, x2, y2 = box
        c = self.canvas
        self._beveled_rect(box, color, CYBER["panel"])
        c.create_text(x1 + 16, y1 + 22, text=title, anchor="w", fill=color, font=("Consolas", 14, "bold"))
        c.create_text(x1 + 16, y1 + 50, text=subtitle[:32], anchor="w", fill=CYBER["text"], font=("Consolas", 9, "bold"))
        state = "ONLINE" if active else "STANDBY"
        pill = CYBER["acid"] if active else CYBER["muted"]
        c.create_rectangle(x1 + 16, y2 - 38, x1 + 104, y2 - 14, fill=CYBER["panel2"], outline=pill, width=1)
        c.create_text(x1 + 60, y2 - 26, text=state, anchor="center", fill=pill, font=("Consolas", 9, "bold"))
        c.create_oval(x2 - 50, y2 - 48, x2 - 18, y2 - 16, outline=color, width=2)
        c.create_oval(x2 - 40, y2 - 38, x2 - 28, y2 - 26, outline=CYBER["text"], width=2)

    def _portal(self, x: int, y: int, color: str) -> None:
        c = self.canvas
        c.create_oval(x - 18, y - 18, x + 18, y + 18, outline=color, width=2)
        c.create_line(x - 28, y, x + 28, y, fill=color, width=1)
        c.create_line(x, y - 28, x, y + 28, fill=color, width=1)

    def _scanlines(self, w: int, h: int) -> None:
        return

    def _connect(self) -> None:
        if not self.server_active:
            self._log("Server OFF: attiva SERVER ON prima di connettere un client.")
            self._refresh_server_toggle()
            return
        if not self._token_valid():
            return
        self.client_badge.configure(text=f"{self._client_direction().upper()} NODE // {self._client_host()}")
        self.link.connect(self._client_host(), self._client_port(), self._token(), self._identity())

    def _auto_connect(self) -> None:
        if not self.server_active or self.auto_retry_started:
            return
        self.auto_retry_started = True
        self.root.after(600, self._connect)
        self.root.after(5000, self._auto_retry)

    def _auto_retry(self) -> None:
        if not self.server_active:
            self.auto_retry_started = False
            return
        if not self.link.connected and not self.link.connecting:
            self._connect()
        self.root.after(5000, self._auto_retry)

    def _change_lang(self, _event=None) -> None:
        self.lang = LANG_VALUES.get(self.lang_box.get(), "it")
        self.config["language"] = self.lang
        (app_dir() / "config.json").write_text(json.dumps(self.config, indent=2), encoding="utf-8")
        self._log(f"Lingua impostata: {self.lang}. Riavvia la UI per aggiornare tutte le etichette.")

    def _show_pointer_hint(self, payload: dict) -> None:
        self.pointer_hint = payload
        self.pointer_hint_until = time.monotonic() + 4.0
        scope = str(payload.get("scope", "server")).upper()
        x = payload.get("x")
        y = payload.get("y")
        screen = payload.get("screen", "")
        self.status.configure(text=f"POINTER {scope} X={x} Y={y}", fg=CYBER["yellow"])
        self._log(f"Pointer locator: {scope} x={x} y={y} screen={screen}")
        self._draw_layout()

    def _tick(self) -> None:
        while True:
            try:
                kind, payload = self.events.get_nowait()
            except queue.Empty:
                break
            if kind == "log":
                self._log(str(payload))
            elif kind == "frame":
                self._handle_frame(payload)
            elif kind == "discovery":
                self._handle_discovery(payload)
            elif kind == "relay":
                event, subject, body = payload
                self._relay_event(event, subject, body)
            elif kind == "remote":
                self.status.configure(text="REMOTE" if payload else self.text["status_connected"])
                self._draw_layout()
            elif kind == "pointer":
                self._show_pointer_hint(payload)
            elif kind == "select":
                self.selected_client = str(payload)
                self._refresh_client_list()
                self._draw_layout()
            elif kind == "disconnected":
                if self.engine.remote:
                    self.engine.release()
                if self.server_active:
                    self.status.configure(text=self.text["status_disconnected"], fg="#ff5c7a")
                else:
                    self.status.configure(text="CLIENT MODE", fg=CYBER["yellow"])
                self._draw_layout()
        self.root.after(80, self._tick)

    def _handle_frame(self, message: dict) -> None:
        kind = message.get("type")
        payload = message.get("payload", {})
        if kind == "hello":
            self.status.configure(text=self.text["status_connected"], fg="#39e58c")
            self._log(f"Client: {payload.get('name')} {payload.get('width')}x{payload.get('height')}")
            if self.pending_take_direction and self.server_active:
                direction = self.pending_take_direction
                entry = self.pending_take_entry
                self.pending_take_direction = None
                self.pending_take_entry = None
                self.root.after(120, lambda d=direction, e=entry: self.engine.take(d, e))
            self._draw_layout()
        elif kind == "edge":
            edge = str(payload.get("edge", ""))
            self._log(f"Il client ha raggiunto il bordo {edge}: valuto ritorno/routing.")
            self.engine.client_edge(edge)
        elif kind == "pulse_ack":
            self._log("Pulse OK dal client.")
        elif kind == "pointer_position":
            payload["scope"] = payload.get("name", "client")
            self._show_pointer_hint(payload)
        elif kind == "entered":
            self._log(
                f"Pointer client attivo: edge={payload.get('edge')} "
                f"x={payload.get('x')} y={payload.get('y')} screen={payload.get('screen')}"
            )
        elif kind == "clipboard_ack":
            self._log(f"Clipboard ACK: {payload}")
        elif kind == "clipboard_text":
            text = str(payload.get("text", ""))
            if self._clipboard_config().get("enabled"):
                self._set_local_clipboard_text(text)
                self._log(f"Clipboard testo ricevuto dal client: {len(text.encode('utf-8'))} byte.")
        elif kind == "file_begin":
            clip = self._clipboard_config()
            transfer_id = str(payload.get("transfer_id", ""))
            size = int(payload.get("size", 0))
            if not clip.get("files_enabled") or not transfer_id or size > int(clip.get("max_file_bytes", 5 * 1024 * 1024)):
                self._log("File in ingresso rifiutato: clipboard file disattivata o dimensione non valida.")
                return
            inbox = Path(os.environ.get("USERPROFILE", str(Path.home()))) / "Downloads" / str(clip.get("inbox_dir", "KyMoRem Inbox"))
            inbox.mkdir(parents=True, exist_ok=True)
            target = inbox / safe_filename(str(payload.get("name", "kymorem-file")))
            self.file_transfers[transfer_id] = {"path": target, "handle": target.open("wb"), "size": size, "received": 0}
            self._log(f"Ricezione file avviata: {target.name} ({size} byte)")
        elif kind == "file_chunk":
            transfer_id = str(payload.get("transfer_id", ""))
            transfer = self.file_transfers.get(transfer_id)
            if not transfer:
                return
            data = base64.b64decode(str(payload.get("data", "")), validate=True)
            transfer["received"] += len(data)
            if transfer["received"] > transfer["size"]:
                transfer["handle"].close()
                self.file_transfers.pop(transfer_id, None)
                self._log("File in ingresso rifiutato: dimensione oltre dichiarato.")
                return
            transfer["handle"].write(data)
        elif kind == "file_end":
            transfer_id = str(payload.get("transfer_id", ""))
            transfer = self.file_transfers.pop(transfer_id, None)
            if not transfer:
                return
            transfer["handle"].close()
            if transfer["received"] == transfer["size"]:
                self._set_local_clipboard_text(str(transfer["path"]))
                self._log(f"File ricevuto: {transfer['path']}")
            else:
                self._log("File ricevuto scartato: dimensione finale non valida.")
        elif kind == "file_ack":
            self._log(f"File transfer ACK: {payload}")
        elif kind == "error":
            self._log(f"Errore client: {payload.get('message')}")
        else:
            self._log(f"{kind}: {payload}")

    def _log(self, message: str) -> None:
        line = time.strftime("%H:%M:%S ") + message
        self.log.insert("end", line + "\n")
        self.log.see("end")
        try:
            with (app_dir() / "server.log").open("a", encoding="utf-8") as handle:
                handle.write(line + "\n")
        except OSError:
            pass

    def run(self) -> None:
        self.root.mainloop()
        self.engine.stop()
        self._stop_discovery()
        self.link.disconnect()


def run_embedded_client(argv: list[str]) -> int:
    from kymorem_windows_client import main as windows_client_main

    client_argv = list(argv)
    has_token_arg = any(item in {"--token", "--token-file"} or item.startswith("--token=") or item.startswith("--token-file=") for item in client_argv)
    if not has_token_arg and not os.environ.get("KYMOREM_TOKEN"):
        try:
            saved = json.loads((app_dir() / "config.json").read_text(encoding="utf-8-sig"))
            token = str(saved.get("token", "")).strip()
            if token:
                client_argv.extend(["--token", token])
        except (OSError, json.JSONDecodeError):
            pass

    original_argv = sys.argv[:]
    try:
        sys.argv = [original_argv[0], *client_argv]
        return int(windows_client_main())
    finally:
        sys.argv = original_argv


def main(argv: list[str] | None = None) -> int:
    raw_argv = list(sys.argv[1:] if argv is None else argv)
    if "--client" in raw_argv and any(item in {"-h", "--help"} for item in raw_argv):
        return run_embedded_client([item for item in raw_argv if item != "--client"])

    parser = argparse.ArgumentParser(description="KyMoRem server UI and embedded client")
    parser.add_argument("--client", action="store_true", help="run KyMoRem as a direct Windows client receiver")
    args, remaining = parser.parse_known_args(raw_argv)

    if args.client and any(item in {"-h", "--help"} for item in remaining):
        return run_embedded_client(remaining)

    terminate_previous_instances()
    if not acquire_single_instance():
        terminate_previous_instances()
        time.sleep(0.8)
        if not acquire_single_instance():
            return 75

    if args.client:
        return run_embedded_client(remaining)

    KyMoRemApp().run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
