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
SM_XVIRTUALSCREEN = 76
SM_YVIRTUALSCREEN = 77
SM_CXVIRTUALSCREEN = 78
SM_CYVIRTUALSCREEN = 79
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
LLMHF_INJECTED = 0x00000001
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
LANG_LABELS = {"it": "Italiano", "en": "English", "ch": "Swiss"}
LANG_VALUES = {value: key for key, value in LANG_LABELS.items()}
THEME_LABELS = {key: key.replace("_", " ").title() for key in THEMES}
THEME_VALUES = {value: key for key, value in THEME_LABELS.items()}

POSITION_TO_GRID = {
    "left": (-1, 0),
    "right": (1, 0),
    "up": (0, -1),
    "down": (0, 1),
    "left/up": (-1, -1),
    "right/up": (1, -1),
    "left/down": (-1, 1),
    "right/down": (1, 1),
}
GRID_TO_POSITION = {value: key for key, value in POSITION_TO_GRID.items()}
POSITION_LABELS = {
    "left": "Left",
    "right": "Right",
    "up": "Up",
    "down": "Down",
    "left/up": "Left + Up",
    "right/up": "Right + Up",
    "left/down": "Left + Down",
    "right/down": "Right + Down",
}
POSITION_VALUES = {value: key for key, value in POSITION_LABELS.items()}
RETURN_EDGE = {"right": "left", "left": "right", "up": "down", "down": "up"}
EDGE_DELTAS = {"right": (1, 0), "left": (-1, 0), "up": (0, -1), "down": (0, 1)}
MAX_CLIENTS = 9
MIN_EDGE_INTERVAL = 0.45
RELEASE_EDGE_MARGIN = 32
EDGE_TRIGGER_INSET = 3
EDGE_CORNER_GUARD = 10
DISCOVERY_CLIENT_TTL = 18.0
DISCOVERY_CONFIG_TTL = 45.0
CLIENT_HEALTH_PROBE_INTERVAL = 12.0
CLIENT_HEALTH_TTL = 36.0
CLIENT_HEALTH_OFFLINE_GRACE = 180.0
CLIENT_HEALTH_TIMEOUT = 2.5
PENDING_CLIENT_HOSTS = {"", "pending", "auto", "discover", "dhcp"}
STARTUP_ALPHA = 0.90
STARTUP_ASPECT = 16 / 9
INPUT_FLUSH_INTERVAL = 1 / 60
WHEEL_FLUSH_INTERVAL = 1 / 30
MAX_DISCRETE_INPUT_BURST = 96
MAX_WHEEL_STEPS_PER_FLUSH = 3
MAX_PENDING_WHEEL_STEPS = 6
NETWORK_FLUSH_INTERVAL = 1 / 60
NETWORK_WHEEL_FLUSH_INTERVAL = 1 / 20
MAX_NETWORK_WHEEL_STEPS = 4
MAX_PENDING_NETWORK_WHEEL_STEPS = 4
MAX_NETWORK_QUEUE = 96
NETWORK_SEND_TIMEOUT = 0.75
WHEEL_DELTA_UNIT = 120
PENDING_EDGE_TAKE_TTL = 2.0
PENDING_MANUAL_TAKE_TTL = 15.0
KEEPALIVE_INTERVAL = 12.0
KEEPALIVE_TIMEOUT = 45.0
SAFE_FILENAME = re.compile(r"[^A-Za-z0-9._ -]+")


def get_cursor() -> tuple[int, int]:
    point = POINT()
    user32.GetCursorPos(ctypes.byref(point))
    return point.x, point.y


def set_cursor(x: int, y: int) -> None:
    user32.SetCursorPos(int(x), int(y))


def async_down(vk: int) -> bool:
    return bool(user32.GetAsyncKeyState(vk) & 0x8000)


def screen_rect() -> tuple[int, int, int, int]:
    left = int(user32.GetSystemMetrics(SM_XVIRTUALSCREEN))
    top = int(user32.GetSystemMetrics(SM_YVIRTUALSCREEN))
    width = int(user32.GetSystemMetrics(SM_CXVIRTUALSCREEN))
    height = int(user32.GetSystemMetrics(SM_CYVIRTUALSCREEN))
    if width <= 0 or height <= 0:
        return 0, 0, int(user32.GetSystemMetrics(0)), int(user32.GetSystemMetrics(1))
    return left, top, width, height


def screen_size() -> tuple[int, int]:
    _left, _top, width, height = screen_rect()
    return width, height


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


def centered_child_geometry(
    parent_x: int,
    parent_y: int,
    parent_w: int,
    parent_h: int,
    child_w: int,
    child_h: int,
    screen_x: int,
    screen_y: int,
    screen_w: int,
    screen_h: int,
) -> str:
    x = int(parent_x) + max(0, int(parent_w) - int(child_w)) // 2
    y = int(parent_y) + max(0, int(parent_h) - int(child_h)) // 2
    max_x = int(screen_x) + max(0, int(screen_w) - int(child_w))
    max_y = int(screen_y) + max(0, int(screen_h) - int(child_h))
    x = max(int(screen_x), min(max_x, x))
    y = max(int(screen_y), min(max_y, y))
    return f"{int(child_w)}x{int(child_h)}+{x}+{y}"


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


def client_endpoint(client: dict) -> tuple[str, int]:
    host = str(client.get("host", ""))
    try:
        port = int(client.get("port", PORT))
    except (TypeError, ValueError):
        port = PORT
    return host, port


def client_key(client: dict) -> str:
    host, port = client_endpoint(client)
    return f"{host}:{port}"


def endpoint_key(endpoint: tuple[str, int] | None) -> str:
    if not endpoint:
        return ""
    host, port = endpoint
    return f"{host}:{int(port)}"


def is_pending_client_host(host: str) -> bool:
    return str(host or "").strip().lower() in PENDING_CLIENT_HOSTS


def pending_client_by_name(clients: list[dict], name: str, port: int) -> dict | None:
    normalized_name = str(name or "").strip().lower()
    if not normalized_name:
        return None
    for client in clients:
        if not bool(client.get("enabled", True)):
            continue
        if str(client.get("name", "")).strip().lower() != normalized_name:
            continue
        try:
            client_port = int(client.get("port", PORT))
        except (TypeError, ValueError):
            client_port = PORT
        if client_port == int(port) and is_pending_client_host(str(client.get("host", ""))):
            return client
    return None


def is_test_client(client: dict | None = None, *, name: str = "", host: str = "") -> bool:
    values = []
    if client:
        values.extend([str(client.get("name", "")), str(client.get("host", ""))])
    values.extend([name, host])
    joined = " ".join(values).lower()
    return "smoke" in joined or "test-smoke" in joined


def grid_from_position(position: str) -> tuple[int, int]:
    raw = str(position)
    key = POSITION_VALUES.get(raw, raw)
    return POSITION_TO_GRID.get(key, (1, 0))


def position_from_grid(x: int, y: int) -> str:
    sx = -1 if x < 0 else 1 if x > 0 else 0
    sy = -1 if y < 0 else 1 if y > 0 else 0
    if (sx, sy) in GRID_TO_POSITION:
        return GRID_TO_POSITION[(sx, sy)]
    if sx:
        return "right" if sx > 0 else "left"
    if not sy:
        return "right"
    return "down" if sy > 0 else "up"


def position_label_from_grid(x: int, y: int) -> str:
    return POSITION_LABELS.get(position_from_grid(x, y), POSITION_LABELS["right"])


def client_edges_from_grid(x: int, y: int) -> list[str]:
    edges: list[str] = []
    if x < 0:
        edges.append("left")
    elif x > 0:
        edges.append("right")
    if y < 0:
        edges.append("up")
    elif y > 0:
        edges.append("down")
    return edges or ["right"]


def client_grid(client: dict) -> tuple[int, int]:
    try:
        return int(client.get("x", 1)), int(client.get("y", 0))
    except (TypeError, ValueError):
        return 1, 0


def ratio_from_axis(value, origin: int, length: int) -> float:
    try:
        raw = (float(value) - float(origin)) / max(1.0, float(length) - 1.0)
    except (TypeError, ValueError):
        raw = 0.5
    return max(0.0, min(1.0, raw))


def parse_screen_dimensions(value: str) -> tuple[int, int]:
    match = re.search(r"(\d+)\s*x\s*(\d+)", str(value or ""))
    if not match:
        return 0, 0
    return int(match.group(1)), int(match.group(2))


def edge_entry_from_client_payload(edge: str, payload: dict, fallback: dict | None = None) -> dict:
    fallback = fallback or {}
    width, height = parse_screen_dimensions(str(payload.get("screen", "") or fallback.get("screen", "")))
    try:
        width = int(payload.get("width", fallback.get("width", width)) or width)
    except (TypeError, ValueError):
        width = 0
    try:
        height = int(payload.get("height", fallback.get("height", height)) or height)
    except (TypeError, ValueError):
        height = 0
    try:
        left = int(payload.get("left", fallback.get("left", 0)) or 0)
    except (TypeError, ValueError):
        left = 0
    try:
        top = int(payload.get("top", fallback.get("top", 0)) or 0)
    except (TypeError, ValueError):
        top = 0
    return {
        "direction": edge,
        "x_ratio": ratio_from_axis(payload.get("x"), left, width),
        "y_ratio": ratio_from_axis(payload.get("y"), top, height),
        "ts": time.monotonic(),
        "source": "client_edge",
    }


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


def is_selectable_client(client: dict) -> bool:
    source = str(client.get("source", "manual")).lower()
    return bool(client.get("enabled", True)) and source != "discovery_pending"


def reserve_client_position(client: dict, clients: list[dict], exclude_key: str = "") -> dict:
    candidate = normalize_client(client)
    occupied = {
        (int(item.get("x", 0)), int(item.get("y", 0)))
        for item in clients
        if client_key(item) != exclude_key and is_selectable_client(item)
    }
    x, y = client_grid(candidate)
    if (x, y) not in occupied:
        return candidate
    step_x = -1 if x < 0 else 1 if x > 0 else 0
    step_y = -1 if y < 0 else 1 if y > 0 else 0
    if step_x == 0 and step_y == 0:
        step_x = 1
    for distance in range(1, 5):
        next_x = step_x * distance if step_x else 0
        next_y = step_y * distance if step_y else 0
        if (next_x, next_y) not in occupied and (next_x, next_y) != (0, 0):
            candidate["x"] = next_x
            candidate["y"] = next_y
            candidate["position"] = position_from_grid(next_x, next_y)
            return candidate
    next_x, next_y = next_free_position([item for item in clients if client_key(item) != exclude_key])
    candidate["x"] = next_x
    candidate["y"] = next_y
    candidate["position"] = position_from_grid(next_x, next_y)
    return candidate


def normalize_layout_clients(clients: list[dict]) -> list[dict]:
    normalized: list[dict] = []
    for index, client in enumerate(clients):
        candidate = normalize_client(client, index)
        if not is_selectable_client(candidate):
            normalized.append(candidate)
            continue
        normalized.append(reserve_client_position(candidate, normalized, client_key(candidate)))
    return normalized


def probe_secure_client(host: str, port: int, token: str, timeout: float = CLIENT_HEALTH_TIMEOUT) -> dict:
    started = time.monotonic()
    result = {
        "key": f"{host}:{int(port)}",
        "host": host,
        "port": int(port),
        "state": "offline",
        "source": "secure_probe",
        "detail": "",
        "latency_ms": 0,
        "seen": time.time(),
    }
    sock: socket.socket | None = None
    try:
        sock = socket.create_connection((host, int(port)), timeout=timeout)
        sock.settimeout(timeout)
        link = secure_connect(sock, token, {"role": "health", "name": "KyMoRem health", "version": VERSION})
        peer = dict(getattr(link, "peer", {}) or {})
        result.update(
            {
                "state": "online",
                "source": "secure_probe",
                "detail": str(peer.get("name") or peer.get("role") or "secure"),
                "name": str(peer.get("name", "")),
                "platform": str(peer.get("platform", "")),
                "version": str(peer.get("version", "")),
                "latency_ms": int((time.monotonic() - started) * 1000),
                "seen": time.time(),
            }
        )
        try:
            link.send(frame("health_probe"))
            link.send(frame("release"))
        except Exception:
            pass
    except Exception as exc:
        result["detail"] = str(exc)
        result["latency_ms"] = int((time.monotonic() - started) * 1000)
        result["seen"] = time.time()
    finally:
        if sock:
            try:
                sock.close()
            except OSError:
                pass
    return result


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
    for key in ["security", "clipboard", "discovery", "email_relay", "ui"]:
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
        config["language"] = "it"
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
    try:
        opacity = float(config.get("ui", {}).get("opacity", STARTUP_ALPHA))
    except (TypeError, ValueError):
        opacity = STARTUP_ALPHA
    opacity = max(0.35, min(1.0, opacity))
    if opacity != config.get("ui", {}).get("opacity"):
        config.setdefault("ui", {})["opacity"] = opacity
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
        self.net_lock = threading.Lock()
        self.send_queue: queue.Queue = queue.Queue(maxsize=MAX_NETWORK_QUEUE)
        self.pending_net_move_dx = 0
        self.pending_net_move_dy = 0
        self.pending_net_wheel_dx = 0
        self.pending_net_wheel_dy = 0
        self.last_network_wheel_flush_ts = 0.0
        self.last_network_drop_log = 0.0
        self.connected = False
        self.connecting = False
        self.client_info: dict = {}
        self.endpoint: tuple[str, int] | None = None
        self.connect_generation = 0
        self.running = True
        self.sender_thread = threading.Thread(target=self._sender_loop, daemon=True)
        self.sender_thread.start()

    def connect(self, host: str, port: int, token: str, identity: dict) -> None:
        self.disconnect()
        with self.lock:
            if self.connected or self.connecting:
                return
            self.connecting = True
            self.client_info = {}
            self.connect_generation += 1
            generation = self.connect_generation
        thread = threading.Thread(target=self._connect_thread, args=(generation, host, port, token, identity), daemon=True)
        thread.start()

    def _connect_thread(self, generation: int, host: str, port: int, token: str, identity: dict) -> None:
        try:
            self.events.put(("log", f"Connessione a {host}:{port}..."))
            sock = socket.create_connection((host, port), timeout=5)
            sock.settimeout(None)
            secure = secure_connect(sock, token, identity)
            with self.lock:
                if generation != self.connect_generation or not self.connecting:
                    try:
                        secure.send(frame("release"))
                    except Exception:
                        pass
                    sock.close()
                    return
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
            with self.lock:
                current_generation = generation == self.connect_generation
            if current_generation:
                self.events.put(("log", f"Sicurezza handshake fallita: {exc}"))
                self.events.put(("relay", ("security_error", "KyMoRem secure handshake failed", str(exc))))
        except Exception as exc:
            with self.lock:
                current_generation = generation == self.connect_generation
            if current_generation:
                self.events.put(("log", f"Connessione fallita: {exc}"))
        finally:
            with self.lock:
                current_generation = generation == self.connect_generation
                if not current_generation:
                    was_connected = False
                else:
                    was_connected = self.connected
                    self.connecting = False
                    self.connected = False
                    self.sock = None
                    self.secure = None
                    self.endpoint = None
            if current_generation:
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
            self.client_info = {}
            self.endpoint = None
            self.connect_generation += 1
        self._clear_network_backlog()
        if sock:
            try:
                if secure:
                    secure.send(frame("release"))
                sock.close()
            except Exception:
                pass

    def send(self, kind: str, **payload) -> None:
        if kind == "move":
            with self.net_lock:
                self.pending_net_move_dx += int(payload.get("dx", 0))
                self.pending_net_move_dy += int(payload.get("dy", 0))
            return
        if kind == "wheel":
            with self.net_lock:
                self.pending_net_wheel_dx = self._cap_network_wheel(
                    self.pending_net_wheel_dx + int(payload.get("dx", 0))
                )
                self.pending_net_wheel_dy = self._cap_network_wheel(
                    self.pending_net_wheel_dy + int(payload.get("dy", 0))
                )
            return
        item = frame(kind, **payload)
        reliable = kind not in {"keepalive", "locate_pointer"}
        if reliable:
            try:
                self.send_queue.put(item, timeout=0.25)
            except queue.Full:
                self._drop_queued_nonessential()
                try:
                    self.send_queue.put(item, timeout=0.25)
                except queue.Full:
                    self._log_network_drop("Coda rete piena: frame affidabile non inviato.")
        else:
            try:
                self.send_queue.put_nowait(item)
            except queue.Full:
                self._log_network_drop("Coda rete piena: frame realtime scartato.")

    def _send_immediate(self, message: dict) -> None:
        with self.lock:
            secure = self.secure
            sock = self.sock
        if not secure:
            return
        try:
            with self.send_lock:
                old_timeout = sock.gettimeout() if sock else None
                if sock:
                    sock.settimeout(NETWORK_SEND_TIMEOUT)
                secure.send(message)
                if sock:
                    sock.settimeout(old_timeout)
        except Exception as exc:
            self.events.put(("log", f"Invio fallito: {exc}"))
            self.disconnect()

    def _sender_loop(self) -> None:
        next_flush = time.monotonic()
        while self.running:
            now = time.monotonic()
            if now >= next_flush:
                self._flush_realtime_network_inputs()
                next_flush = now + NETWORK_FLUSH_INTERVAL
            try:
                message = self.send_queue.get(timeout=0.01)
            except queue.Empty:
                continue
            self._send_immediate(message)

    def _cap_network_wheel(self, value: int) -> int:
        limit = MAX_PENDING_NETWORK_WHEEL_STEPS * WHEEL_DELTA_UNIT
        return max(-limit, min(limit, int(value)))

    def _take_network_wheel_batch(self, attr: str) -> int:
        pending = int(getattr(self, attr))
        steps = int(pending / WHEEL_DELTA_UNIT)
        if steps == 0:
            return 0
        steps = max(-MAX_NETWORK_WHEEL_STEPS, min(MAX_NETWORK_WHEEL_STEPS, steps))
        delta = steps * WHEEL_DELTA_UNIT
        setattr(self, attr, pending - delta)
        return delta

    def _flush_realtime_network_inputs(self) -> None:
        with self.lock:
            if not self.connected:
                self._clear_network_backlog()
                return
        now = time.monotonic()
        include_wheel = now - self.last_network_wheel_flush_ts >= NETWORK_WHEEL_FLUSH_INTERVAL
        with self.net_lock:
            dx = self.pending_net_move_dx
            dy = self.pending_net_move_dy
            self.pending_net_move_dx = 0
            self.pending_net_move_dy = 0
            wheel_dx = self._take_network_wheel_batch("pending_net_wheel_dx") if include_wheel else 0
            wheel_dy = self._take_network_wheel_batch("pending_net_wheel_dy") if include_wheel else 0
        if dx or dy:
            self._send_immediate(frame("move", dx=dx, dy=dy))
        if wheel_dx or wheel_dy:
            self._send_immediate(frame("wheel", dx=wheel_dx, dy=wheel_dy))
            self.last_network_wheel_flush_ts = now

    def _clear_network_backlog(self) -> None:
        with self.net_lock:
            self.pending_net_move_dx = 0
            self.pending_net_move_dy = 0
            self.pending_net_wheel_dx = 0
            self.pending_net_wheel_dy = 0
        while True:
            try:
                self.send_queue.get_nowait()
            except queue.Empty:
                break

    def _drop_queued_nonessential(self) -> None:
        kept: list[dict] = []
        while True:
            try:
                message = self.send_queue.get_nowait()
            except queue.Empty:
                break
            if message.get("type") in {"keepalive", "locate_pointer"}:
                continue
            kept.append(message)
        for message in kept[-MAX_NETWORK_QUEUE // 2:]:
            try:
                self.send_queue.put_nowait(message)
            except queue.Full:
                break

    def _log_network_drop(self, message: str) -> None:
        now = time.monotonic()
        if now - self.last_network_drop_log > 1.0:
            self.last_network_drop_log = now
            self.events.put(("log", message))


class ThemedSelect(ttk.Combobox):
    def __init__(self, parent, values, width=14, textvariable=None):
        self.variable = textvariable or tk.StringVar(value=values[0] if values else "")
        self.values = list(values)
        super().__init__(
            parent,
            textvariable=self.variable,
            values=self.values,
            state="readonly",
            width=width,
            style="Kmr.TCombobox",
            font=("Consolas", 10, "bold"),
        )
        self.configure(takefocus=True, exportselection=False)
        self.bind("<Button-1>", self._open_dropdown)
        self.bind("<Alt-Down>", self._open_dropdown, add="+")
        self.bind("<F4>", self._open_dropdown, add="+")

    def set_values(self, values) -> None:
        self.values = list(values)
        self.configure(values=self.values)

    def _open_dropdown(self, _event=None):
        self.focus_set()
        try:
            self.tk.call("ttk::combobox::Post", self._w)
        except tk.TclError:
            self.event_generate("<Alt-Down>")
        return "break"

    def set(self, value) -> None:
        self.variable.set(value)


class ControlEngine:
    def __init__(self, link: RemoteLink, events: queue.Queue, router=None, edge_guard=None, enabled: bool = False):
        self.link = link
        self.events = events
        self.router = router
        self.edge_guard = edge_guard
        self.enabled = enabled
        self.remote = False
        self.running = True
        self.left, self.top, self.w, self.h = screen_rect()
        self.anchor = (self.left + self.w // 2, self.top + self.h // 2)
        self.active_direction = "right"
        self.last_edge_ts = 0.0
        self.edge_exit = {
            "direction": "right",
            "x": self.left + self.w - 1,
            "y": self.top + self.h // 2,
            "x_ratio": 1.0,
            "y_ratio": 0.5,
            "ts": 0.0,
        }
        self.cursor_hidden = False
        self.last_mouse_point = self.anchor
        self.suppress_mouse_move = False
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
        self.input_queue: queue.Queue = queue.Queue(maxsize=1024)
        self.coalesce_lock = threading.Lock()
        self.pending_move_dx = 0
        self.pending_move_dy = 0
        self.pending_wheel_dx = 0
        self.pending_wheel_dy = 0
        self.last_wheel_flush_ts = 0.0
        self.last_input_drop_log = 0.0
        now = time.monotonic()
        self.last_keepalive_sent = now
        self.last_keepalive_ack = now
        self.input_thread = threading.Thread(target=self._input_sender_loop, daemon=True)
        self.input_thread.start()
        self.hook_thread = threading.Thread(target=self._hook_loop, daemon=True)
        self.hook_thread.start()
        self.thread = threading.Thread(target=self.loop, daemon=True)
        self.thread.start()

    def _queue_remote(self, kind: str, **payload) -> None:
        if kind == "move":
            with self.coalesce_lock:
                self.pending_move_dx += int(payload.get("dx", 0))
                self.pending_move_dy += int(payload.get("dy", 0))
            return
        if kind == "wheel":
            with self.coalesce_lock:
                self.pending_wheel_dx = self._cap_pending_wheel(
                    self.pending_wheel_dx + int(payload.get("dx", 0))
                )
                self.pending_wheel_dy = self._cap_pending_wheel(
                    self.pending_wheel_dy + int(payload.get("dy", 0))
                )
            return
        try:
            self.input_queue.put_nowait((kind, payload))
        except queue.Full:
            now = time.monotonic()
            if now - self.last_input_drop_log > 1.0:
                self.last_input_drop_log = now
                self.events.put(("log", "Input remoto discreto scartato: coda piena."))

    def _cap_pending_wheel(self, value: int) -> int:
        limit = MAX_PENDING_WHEEL_STEPS * WHEEL_DELTA_UNIT
        return max(-limit, min(limit, int(value)))

    def _take_wheel_batch(self, attr: str) -> int:
        pending = int(getattr(self, attr))
        steps = int(pending / WHEEL_DELTA_UNIT)
        if steps == 0:
            return 0
        steps = max(-MAX_WHEEL_STEPS_PER_FLUSH, min(MAX_WHEEL_STEPS_PER_FLUSH, steps))
        delta = steps * WHEEL_DELTA_UNIT
        setattr(self, attr, pending - delta)
        return delta

    def _clear_pending_inputs(self) -> None:
        with self.coalesce_lock:
            self.pending_move_dx = 0
            self.pending_move_dy = 0
            self.pending_wheel_dx = 0
            self.pending_wheel_dy = 0
        while True:
            try:
                self.input_queue.get_nowait()
            except queue.Empty:
                break

    def _take_coalesced_inputs(self, *, include_wheel: bool = True) -> tuple[int, int, int, int]:
        with self.coalesce_lock:
            dx = self.pending_move_dx
            dy = self.pending_move_dy
            self.pending_move_dx = 0
            self.pending_move_dy = 0
            wheel_dx = self._take_wheel_batch("pending_wheel_dx") if include_wheel else 0
            wheel_dy = self._take_wheel_batch("pending_wheel_dy") if include_wheel else 0
        return dx, dy, wheel_dx, wheel_dy

    def _flush_coalesced_inputs(self) -> None:
        if not self.remote:
            self._clear_pending_inputs()
            return
        now = time.monotonic()
        include_wheel = now - self.last_wheel_flush_ts >= WHEEL_FLUSH_INTERVAL
        dx, dy, wheel_dx, wheel_dy = self._take_coalesced_inputs(include_wheel=include_wheel)
        if dx or dy:
            self.link.send("move", dx=dx, dy=dy)
        if wheel_dx or wheel_dy:
            self.link.send("wheel", dx=wheel_dx, dy=wheel_dy)
            self.last_wheel_flush_ts = now

    def _input_sender_loop(self) -> None:
        next_flush = time.monotonic()
        while self.running:
            now = time.monotonic()
            if now >= next_flush:
                try:
                    self._flush_coalesced_inputs()
                except Exception as exc:
                    self.events.put(("log", f"Invio input remoto fallito: {exc}"))
                next_flush = now + INPUT_FLUSH_INTERVAL

            sent = 0
            while sent < MAX_DISCRETE_INPUT_BURST:
                try:
                    kind, payload = self.input_queue.get_nowait()
                except queue.Empty:
                    break
                if self.remote:
                    try:
                        self.link.send(kind, **payload)
                    except Exception as exc:
                        self.events.put(("log", f"Invio input remoto fallito: {exc}"))
                        break
                sent += 1
            time.sleep(0.004)

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
            info = ctypes.cast(l_param, ctypes.POINTER(MSLLHOOKSTRUCT)).contents
            if msg == WM_MOUSEMOVE:
                x, y = int(info.pt.x), int(info.pt.y)
                if self.suppress_mouse_move or int(info.flags) & LLMHF_INJECTED:
                    self.suppress_mouse_move = False
                    self.last_mouse_point = self.anchor
                    return 1
                last_x, last_y = self.last_mouse_point
                dx = x - int(last_x)
                dy = y - int(last_y)
                if dx or dy:
                    self._queue_remote("move", dx=dx, dy=dy)
                self.last_mouse_point = self.anchor
                if (x, y) != self.anchor:
                    self.suppress_mouse_move = True
                    set_cursor(*self.anchor)
                return 1
            if msg in MOUSE_BUTTON_MESSAGES:
                button, state = MOUSE_BUTTON_MESSAGES[msg]
                down = state == "down"
                if self.button_state.get(button) != down:
                    self.button_state[button] = down
                    self._queue_remote("button", button=button, state=state)
                return 1
            if msg in {WM_MOUSEWHEEL, WM_MOUSEHWHEEL}:
                delta = ctypes.c_short((int(info.mouseData) >> 16) & 0xFFFF).value
                if delta and msg == WM_MOUSEHWHEEL:
                    self._queue_remote("wheel", dx=delta)
                elif delta:
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
        self._show_host_cursor(force=True)
        self.running = False
        if self.hook_thread_id:
            user32.PostThreadMessageW(self.hook_thread_id, WM_QUIT, 0, 0)

    def _hide_host_cursor(self) -> None:
        if self.cursor_hidden:
            return
        for _ in range(128):
            if user32.ShowCursor(False) < 0:
                break
        self.cursor_hidden = True

    def _show_host_cursor(self, *, force: bool = False) -> None:
        if not self.cursor_hidden and not force:
            return
        count = 0
        for _ in range(128):
            try:
                count = user32.ShowCursor(True)
            except OSError:
                break
            if count >= 0:
                break
        if force:
            while count > 0:
                try:
                    count = user32.ShowCursor(False)
                except OSError:
                    break
        self.cursor_hidden = False

    def _capture_edge_exit(self, direction: str, x: int, y: int) -> dict:
        self.left, self.top, self.w, self.h = screen_rect()
        self.anchor = (self.left + self.w // 2, self.top + self.h // 2)
        entry = {
            "direction": direction,
            "x": int(x),
            "y": int(y),
            "x_ratio": max(0.0, min(1.0, (int(x) - self.left) / max(1, self.w - 1))),
            "y_ratio": max(0.0, min(1.0, (int(y) - self.top) / max(1, self.h - 1))),
            "ts": time.monotonic(),
        }
        self.edge_exit = entry
        return dict(entry)

    def note_keepalive_ack(self) -> None:
        self.last_keepalive_ack = time.monotonic()

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
        now = time.monotonic()
        self.last_keepalive_ack = now
        self.last_keepalive_sent = now
        self.link.send(
            "enter",
            edge=entry_edge,
            source_edge=direction,
            source_x=int(context.get("x", 0)),
            source_y=int(context.get("y", 0)),
            x_ratio=x_ratio,
            y_ratio=y_ratio,
        )
        self._clear_pending_inputs()
        self.last_wheel_flush_ts = 0.0
        self._hide_host_cursor()
        self.last_mouse_point = self.anchor
        self.suppress_mouse_move = True
        self.remote = True
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

    def release(self, *, notify_client: bool = True, restore_cursor: bool = True) -> None:
        if self.remote:
            self.remote = False
            now = time.monotonic()
            self.last_keepalive_ack = now
            self.last_keepalive_sent = now
            self._clear_pending_inputs()
            self._release_remote_inputs()
            self.last_edge_ts = time.monotonic()
            if restore_cursor:
                if self.active_direction == "left":
                    set_cursor(self.left + RELEASE_EDGE_MARGIN, self.top + self.h // 2)
                elif self.active_direction == "up":
                    set_cursor(self.left + self.w // 2, self.top + RELEASE_EDGE_MARGIN)
                elif self.active_direction == "down":
                    set_cursor(self.left + self.w // 2, self.top + max(0, self.h - RELEASE_EDGE_MARGIN))
                else:
                    set_cursor(self.left + max(0, self.w - RELEASE_EDGE_MARGIN), self.top + self.h // 2)
                self._show_host_cursor(force=True)
            if notify_client:
                self.link.send("release")
            self.events.put(("remote", False))
            self.events.put(("log", "Controllo remoto rilasciato."))

    def client_edge(self, edge: str) -> None:
        if RETURN_EDGE.get(self.active_direction, "left") == edge:
            self.release()

    def _host_edge(self, x: int, y: int) -> str | None:
        right_at = self.left + max(0, self.w - EDGE_TRIGGER_INSET)
        down_at = self.top + max(0, self.h - EDGE_TRIGGER_INSET)
        in_top_corner = y <= self.top + EDGE_CORNER_GUARD
        in_bottom_corner = y >= self.top + max(0, self.h - 1 - EDGE_CORNER_GUARD)
        in_left_corner = x <= self.left + EDGE_CORNER_GUARD
        in_right_corner = x >= self.left + max(0, self.w - 1 - EDGE_CORNER_GUARD)
        if x >= right_at and not (in_top_corner or in_bottom_corner):
            return "right"
        if x <= self.left + EDGE_TRIGGER_INSET - 1 and not (in_top_corner or in_bottom_corner):
            return "left"
        if y <= self.top + EDGE_TRIGGER_INSET - 1 and not (in_left_corner or in_right_corner):
            return "up"
        if y >= down_at and not (in_left_corner or in_right_corner):
            return "down"
        return None

    def loop(self) -> None:
        while self.running:
            try:
                self._loop_once()
            except Exception as exc:
                self.events.put(("log", f"Control engine error: {exc}"))
                time.sleep(0.2)

    def _loop_once(self) -> None:
        time.sleep(0.012)
        if not self.enabled:
            if self.remote:
                self.release(notify_client=False)
            return
        if not self.remote:
            x, y = get_cursor()
            direction = self._host_edge(x, y)
            if self.edge_guard and self.edge_guard(x, y) and not direction:
                return
            if direction and time.monotonic() - self.last_edge_ts > MIN_EDGE_INTERVAL:
                self.last_edge_ts = time.monotonic()
                entry = self._capture_edge_exit(direction, x, y)
                if self.router and self.router(direction, entry):
                    self.take(direction, entry)
            return

        if not getattr(self.link, "connected", False):
            self.events.put(("log", "Link remoto non piu' attivo: rilascio controllo locale."))
            self.release(notify_client=False)
            time.sleep(0.2)
            return

        if async_down(VK["VK_CONTROL"]) and async_down(VK["VK_ESCAPE"]):
            self.release()
            time.sleep(0.2)
            return

        now = time.monotonic()
        if now - self.last_keepalive_sent >= KEEPALIVE_INTERVAL:
            self.link.send("keepalive", direction=self.active_direction)
            self.last_keepalive_sent = now
        if now - self.last_keepalive_ack >= KEEPALIVE_TIMEOUT:
            self.events.put(("log", "Sessione remota inattiva troppo a lungo: rilascio locale e rinnovo link."))
            self.release(notify_client=False)
            self.link.disconnect()
            time.sleep(0.2)
            return


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
        self._prune_transient_clients(startup=True)
        self.selected_client = client_key(self._client_config())
        self.drag_client: str | None = None
        self.file_transfers: dict[str, dict] = {}
        self.pointer_hint: dict | None = None
        self.pointer_hint_until = 0.0
        self.next_prune_ts = 0.0
        self.next_health_probe_ts = 0.0
        self.health_probe_running = False
        self.client_health: dict[str, dict] = {}
        self.last_client_edge_log: dict[str, float] = {}
        self.log_history: list[str] = []
        self.last_cursor_recovery_ts = 0.0
        self.cursor_recovery_bound = False
        self.control_center = None
        self.events: queue.Queue = queue.Queue()
        self.link = RemoteLink(self.events)
        self.server_active = bool(self.config.get("mode") == "server" and self.config.get("server_on", False))
        self.auto_retry_started = False
        self.pending_take_direction: str | None = None
        self.pending_take_entry: dict | None = None
        self.pending_take_client: str = ""
        self.pending_take_endpoint: tuple[str, int] | None = None
        self.pending_take_deadline = 0.0
        self.pending_take_requires_edge = False
        self.discovery_beacon = None
        self.discovery_listener = None
        self.tray_icon = None
        self.root = tk.Tk()
        self.engine = ControlEngine(self.link, self.events, self._route_from_edge, self._pointer_inside_ui, enabled=self.server_active)
        self.root.title(f"{APP_NAME} {VERSION} // {APP_SHORT_MARK} Neon Route Console")
        self.root.geometry(self._startup_geometry())
        min_w, min_h = self._surface_minsize()
        self.root.minsize(min_w, min_h)
        self.root.configure(bg=CYBER["bg"])
        try:
            self.root.attributes("-alpha", self._ui_opacity())
            self.root.attributes("-topmost", False)
        except tk.TclError:
            pass
        icon = asset_path("kymorem.ico")
        if icon.exists():
            try:
                self.root.iconbitmap(str(icon))
            except tk.TclError:
                pass
        self.root.protocol("WM_DELETE_WINDOW", self._hide_to_tray)
        self._style()
        self._build()
        self._bind_cursor_recovery()
        self._start_tray()
        self._tick()
        if self.server_active:
            self._start_discovery()
            self._auto_connect()
        else:
            self._log("Modalita client predefinita: server OFF. Usa SERVER ON dalla UI per condividere mouse e tastiera.")

    def _surface_minsize(self) -> tuple[int, int]:
        if self.server_active:
            return 720, 405
        return 480, 280

    def _startup_geometry(self) -> str:
        screen_w = max(1024, int(self.root.winfo_screenwidth()))
        screen_h = max(576, int(self.root.winfo_screenheight()))
        if not self.server_active:
            target_w = min(540, max(480, screen_w // 3))
            target_h = min(320, max(280, screen_h // 3))
            x = max(0, screen_w - target_w - 42)
            y = max(0, screen_h - target_h - 96)
            return f"{target_w}x{target_h}+{x}+{y}"
        target_w = max(720, screen_w // 2)
        target_h = round(target_w / STARTUP_ASPECT)
        half_h = max(405, screen_h // 2)
        if target_h > half_h:
            target_h = half_h
            target_w = round(target_h * STARTUP_ASPECT)
        target_w = min(target_w, max(720, screen_w - 80))
        target_h = min(target_h, max(405, screen_h - 80))
        x = max(0, screen_w - target_w - 36)
        y = max(0, screen_h - target_h - 72)
        return f"{target_w}x{target_h}+{x}+{y}"

    def _ui_config(self) -> dict:
        ui = dict(DEFAULT_CONFIG.get("ui", {}))
        ui.update(self.config.get("ui", {}))
        return ui

    def _ui_opacity(self) -> float:
        try:
            value = float(self._ui_config().get("opacity", STARTUP_ALPHA))
        except (TypeError, ValueError):
            value = STARTUP_ALPHA
        return max(0.35, min(1.0, value))

    def _apply_ui_opacity(self, value: float) -> None:
        value = max(0.35, min(1.0, float(value)))
        try:
            self.root.attributes("-alpha", value)
        except tk.TclError:
            pass
        if hasattr(self, "opacity_value"):
            self.opacity_value.configure(text=f"{round(value * 100)}%")

    def _opacity_changed(self, value) -> None:
        self._apply_ui_opacity(float(value) / 100.0)

    def _save_ui_opacity(self, _event=None) -> None:
        if not hasattr(self, "opacity_var"):
            return
        value = max(35, min(100, int(round(float(self.opacity_var.get())))))
        self.config.setdefault("ui", {})["opacity"] = value / 100.0
        self._apply_ui_opacity(value / 100.0)
        self._save_config()
        self._log(self.text["opacity_saved"].format(value=value))

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

    def _bind_cursor_recovery(self) -> None:
        if self.cursor_recovery_bound:
            return
        self.cursor_recovery_bound = True
        self.root.bind("<Enter>", self._recover_ui_cursor, add="+")
        self.root.bind("<FocusIn>", self._recover_ui_cursor, add="+")
        self.root.bind_all("<Motion>", self._recover_ui_cursor, add="+")

    def _recover_ui_cursor(self, event=None) -> None:
        if getattr(self.engine, "remote", False):
            return
        now = time.monotonic()
        if now - self.last_cursor_recovery_ts < 0.25:
            return
        if event is not None:
            try:
                x = int(getattr(event, "x_root", self.root.winfo_pointerx()))
                y = int(getattr(event, "y_root", self.root.winfo_pointery()))
            except (tk.TclError, ValueError):
                x, y = self.root.winfo_pointerx(), self.root.winfo_pointery()
            if not self._pointer_inside_ui(x, y):
                return
        self.last_cursor_recovery_ts = now
        try:
            self.root.configure(cursor="")
        except tk.TclError:
            pass
        self.engine._show_host_cursor(force=True)

    def _build(self) -> None:
        if self.server_active:
            self._build_server_ui()
        else:
            self._build_client_toolbox()

    def _build_server_ui(self) -> None:
        header = tk.Frame(self.root, bg=CYBER["bg"])
        header.pack(fill="x", padx=24, pady=(18, 10))

        title_box = tk.Frame(header, bg=CYBER["bg"])
        title_box.pack(side="left", fill="x", expand=True)
        tk.Label(
            title_box,
            text="KyMoRem",
            fg=CYBER["cyan"],
            bg=CYBER["bg"],
            font=("Consolas", 34, "bold"),
        ).pack(anchor="w")
        tk.Label(
            title_box,
            text=f"{APP_EXTENDED_NAME} // {APP_SHORT_MARK}",
            fg=CYBER["pink"],
            bg=CYBER["bg"],
            font=("Consolas", 11, "bold"),
        ).pack(anchor="w", pady=(0, 2))
        tk.Label(
            title_box,
            text="MOVE. PLAY. RETURN.",
            fg=CYBER["text"],
            bg=CYBER["bg"],
            font=("Consolas", 11, "bold"),
        ).pack(anchor="w")

        header_actions = tk.Frame(header, bg=CYBER["bg"])
        header_actions.pack(side="right", anchor="n")
        self._mini_button(header_actions, self.text["refresh"].upper(), self._refresh_now, CYBER["yellow"]).pack(side="left", padx=(0, 8))
        self._mini_button(header_actions, "CONTROL CENTER", self._open_control_center, CYBER["cyan"]).pack(side="left", padx=(8, 0))

        summary = tk.Frame(self.root, bg=CYBER["bg"])
        summary.pack(fill="x", padx=24, pady=(0, 10))

        status_card = tk.Frame(summary, bg=CYBER["panel"], highlightthickness=1, highlightbackground=CYBER["line"])
        status_card.pack(side="left", fill="x", expand=True, padx=(0, 8))
        tk.Label(
            status_card,
            text=self.text["node_status"].upper(),
            fg=CYBER["pink"],
            bg=CYBER["panel"],
            font=("Consolas", 12, "bold"),
        ).pack(anchor="w", padx=16, pady=(14, 4))
        self.status = tk.Label(
            status_card,
            text=self.text["boot_ready"].upper(),
            fg=CYBER["acid"],
            bg=CYBER["panel2"],
            font=("Consolas", 12, "bold"),
            padx=12,
            pady=8,
        )
        self.status.pack(fill="x", padx=16, pady=(0, 10))
        self.discovery_badge = tk.Label(
            status_card,
            text=self.text["discovery_off"].upper() if not self.server_active else self.text["discovery_armed"].upper(),
            fg=CYBER["muted"],
            bg=CYBER["panel"],
            font=("Consolas", 9, "bold"),
        )
        self.discovery_badge.pack(anchor="w", padx=16, pady=(0, 12))

        client_card = tk.Frame(summary, bg=CYBER["panel"], highlightthickness=1, highlightbackground=CYBER["line"])
        client_card.pack(side="left", fill="x", expand=True, padx=(8, 0))
        tk.Label(
            client_card,
            text=self.text["client"].upper(),
            fg=CYBER["cyan"],
            bg=CYBER["panel"],
            font=("Consolas", 12, "bold"),
        ).pack(anchor="w", padx=16, pady=(14, 4))
        self.main_client_var = tk.StringVar()
        self.main_client_box = ThemedSelect(client_card, values=[], width=28, textvariable=self.main_client_var)
        self.main_client_box.pack(fill="x", padx=16, pady=(0, 8))
        self.main_client_box.bind("<<ComboboxSelected>>", self._select_client_from_picker)
        self.client_badge = tk.Label(
            client_card,
            text=self._client_badge_text(),
            fg=CYBER["cyan"],
            bg=CYBER["panel"],
            font=("Consolas", 10, "bold"),
            wraplength=420,
            justify="left",
        )
        self.client_badge.pack(anchor="w", padx=16, pady=(0, 8))
        self.signature_badge = tk.Label(
            client_card,
            text=f"{APP_SIGNATURE} // {VERSION}",
            fg=CYBER["yellow"],
            bg=CYBER["panel"],
            font=("Consolas", 9, "bold"),
            wraplength=420,
            justify="left",
        )
        self.signature_badge.pack(anchor="w", padx=16, pady=(0, 12))

        stage = tk.Frame(self.root, bg=CYBER["bg"])
        stage.pack(fill="both", expand=True, padx=24, pady=(0, 10))
        self.canvas = tk.Canvas(stage, bg=CYBER["bg2"], highlightthickness=1, highlightbackground=CYBER["line"])
        self.canvas.pack(fill="both", expand=True)
        self.canvas.bind("<Configure>", lambda _event: self._draw_layout())
        self.canvas.bind("<Button-1>", self._canvas_press)
        self.canvas.bind("<B1-Motion>", self._canvas_drag)
        self.canvas.bind("<ButtonRelease-1>", self._canvas_release)

        controls_shell = tk.Frame(self.root, bg=CYBER["bg"])
        controls_shell.pack(fill="x", padx=24, pady=(0, 6))
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
        self._neon_button(controls, self.text["connect"], self._connect, CYBER["cyan"]).pack(side="left", padx=8)
        self._neon_button(controls, self.text["take"], self._take_selected, CYBER["acid"]).pack(side="left", padx=8)
        self._neon_button(controls, self.text["release"], self.engine.release, CYBER["yellow"]).pack(side="left", padx=8)
        self._neon_button(controls, self.text["disconnect"], self.link.disconnect, CYBER["pink"]).pack(side="left", padx=8)
        self._neon_button(controls, self.text["refresh"], self._refresh_now, CYBER["yellow"]).pack(side="left", padx=8)
        self._neon_button(controls, "CONTROL CENTER", self._open_control_center, CYBER["cyan"]).pack(side="left", padx=8)

        tk.Label(
            self.root,
            text=self.text["footer"],
            fg=CYBER["muted"],
            bg=CYBER["bg"],
            font=("Consolas", 9),
        ).pack(anchor="w", padx=24, pady=(0, 16))
        self._refresh_server_toggle()
        self._refresh_client_list()
        self._draw_layout()

    def _build_client_toolbox(self) -> None:
        card = tk.Frame(self.root, bg=CYBER["panel"], highlightthickness=1, highlightbackground=CYBER["line"])
        card.pack(fill="both", expand=True, padx=24, pady=24)

        header = tk.Frame(card, bg=CYBER["panel"])
        header.pack(fill="x", padx=22, pady=(22, 10))
        tk.Label(
            header,
            text="KyMoRem",
            fg=CYBER["cyan"],
            bg=CYBER["panel"],
            font=("Consolas", 28, "bold"),
        ).pack(anchor="w")
        tk.Label(
            header,
            text="TOOLBOX CLIENT",
            fg=CYBER["pink"],
            bg=CYBER["panel"],
            font=("Consolas", 12, "bold"),
        ).pack(anchor="w", pady=(2, 0))

        self.status = tk.Label(
            card,
            text=self.text["client_mode_route"].upper(),
            fg=CYBER["yellow"],
            bg=CYBER["panel2"],
            font=("Consolas", 12, "bold"),
            padx=12,
            pady=8,
        )
        self.status.pack(fill="x", padx=22, pady=(0, 14))

        rows = tk.Frame(card, bg=CYBER["panel"])
        rows.pack(fill="x", padx=22, pady=(0, 12))

        def _toolbox_row(label: str, value: str) -> None:
            row = tk.Frame(rows, bg=CYBER["panel"])
            row.pack(fill="x", pady=5)
            tk.Label(
                row,
                text=label,
                fg=CYBER["muted"],
                bg=CYBER["panel"],
                font=("Consolas", 9, "bold"),
                width=16,
                anchor="w",
            ).pack(side="left")
            tk.Label(
                row,
                text=value,
                fg=CYBER["text"],
                bg=CYBER["panel2"],
                font=("Consolas", 10, "bold"),
                padx=10,
                pady=6,
                anchor="w",
            ).pack(side="left", fill="x", expand=True)

        _toolbox_row("IP LOCALE", self.local_ip)
        _toolbox_row("IP REMOTO", self._client_host())
        _toolbox_row("PORTA KYMOREM", str(self._client_port()))
        _toolbox_row("ID/PID PROCESSO", self._toolbox_process_id())

        actions = tk.Frame(card, bg=CYBER["panel"])
        actions.pack(fill="x", padx=22, pady=(0, 22))
        self.server_toggle = self._neon_button(actions, "", self._toggle_server, CYBER["acid"])
        self.server_toggle.pack(side="left")
        self._refresh_server_toggle()

    def _open_control_center(self) -> None:
        existing = getattr(self, "control_center", None)
        if existing and existing.winfo_exists():
            existing.deiconify()
            existing.geometry(self._control_center_geometry())
            existing.lift()
            existing.focus_force()
            return

        self.control_center = tk.Toplevel(self.root)
        self.control_center.title(f"{APP_NAME} // Control Center")
        self.control_center.configure(bg=CYBER["bg"])
        self.control_center.geometry(self._control_center_geometry())
        self.control_center.minsize(390, 520)
        try:
            self.control_center.attributes("-alpha", self._ui_opacity())
        except tk.TclError:
            pass
        self.control_center.protocol("WM_DELETE_WINDOW", self._close_control_center)

        shell = tk.Frame(self.control_center, bg=CYBER["bg"])
        shell.pack(fill="both", expand=True, padx=14, pady=14)
        canvas = tk.Canvas(shell, bg=CYBER["panel"], highlightthickness=1, highlightbackground=CYBER["line"])
        scroll = tk.Scrollbar(shell, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=scroll.set)
        canvas.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")

        content = tk.Frame(canvas, bg=CYBER["panel"])
        window_id = canvas.create_window((0, 0), window=content, anchor="nw")

        def _sync_center(_event=None) -> None:
            canvas.configure(scrollregion=canvas.bbox("all"))

        def _resize_center(event) -> None:
            canvas.itemconfigure(window_id, width=max(360, event.width))
            canvas.configure(scrollregion=canvas.bbox("all"))

        content.bind("<Configure>", _sync_center)
        canvas.bind("<Configure>", _resize_center)

        top = tk.Frame(content, bg=CYBER["panel"])
        top.pack(fill="x", padx=18, pady=(18, 12))
        tk.Label(
            top,
            text="CONTROL CENTER",
            fg=CYBER["cyan"],
            bg=CYBER["panel"],
            font=("Consolas", 18, "bold"),
        ).pack(side="left")
        self._mini_button(top, "CLOSE", self._close_control_center, CYBER["pink"]).pack(side="right")

        options = tk.Frame(content, bg=CYBER["panel"])
        options.pack(fill="x", padx=16, pady=(0, 14))

        self.mode_box = ThemedSelect(options, values=list(MODE_VALUES.keys()), width=8)
        self.mode_box.set(MODE_LABELS.get(str(self.config.get("mode", "client")), "Client"))
        self.mode_box.bind("<<ComboboxSelected>>", self._change_mode)
        self.mode_box.pack(side="left", padx=(0, 8))

        self.theme_box = ThemedSelect(options, values=list(THEME_VALUES.keys()), width=18)
        self.theme_box.set(THEME_LABELS.get(self.theme_id, THEME_LABELS["old_school_x11"]))
        self.theme_box.bind("<<ComboboxSelected>>", self._change_theme)
        self.theme_box.pack(side="left", padx=(0, 8))

        self.lang_box = ThemedSelect(options, values=list(LANG_VALUES.keys()), width=10)
        self.lang_box.set(LANG_LABELS.get(self.lang, LANG_LABELS["it"]))
        self.lang_box.bind("<<ComboboxSelected>>", self._change_lang)
        self.lang_box.pack(side="left")

        tk.Label(content, text=self.text["client_map"].upper(), fg=CYBER["cyan"], bg=CYBER["panel"], font=("Consolas", 12, "bold")).pack(anchor="w", padx=18, pady=(0, 6))
        self.client_list = tk.Listbox(
            content,
            height=5,
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

        form = tk.Frame(content, bg=CYBER["panel"])
        form.pack(fill="x", padx=16, pady=(0, 10))
        self.client_name_var = tk.StringVar()
        self.client_host_var = tk.StringVar()
        self.client_port_var = tk.StringVar(value=str(PORT))
        self.client_position_var = tk.StringVar(value=POSITION_LABELS["right"])
        self._field(form, self.text["name"], self.client_name_var, 0)
        self._field(form, self.text["ip"], self.client_host_var, 1)
        self._field(form, self.text["port"], self.client_port_var, 2)
        tk.Label(form, text=self.text["position"].upper(), fg=CYBER["muted"], bg=CYBER["panel"], font=("Consolas", 8, "bold")).grid(row=3, column=0, sticky="w", pady=2)
        self.position_box = ThemedSelect(
            form,
            values=list(POSITION_LABELS.values()),
            width=16,
            textvariable=self.client_position_var,
        )
        self.position_box.grid(row=3, column=1, sticky="ew", pady=2)
        form.columnconfigure(1, weight=1)

        client_buttons = tk.Frame(content, bg=CYBER["panel"])
        client_buttons.pack(fill="x", padx=16, pady=(0, 10))
        self._mini_button(client_buttons, self.text["add"].upper(), self._add_manual_client, CYBER["acid"]).grid(row=0, column=0, padx=2, pady=2, sticky="ew")
        self._mini_button(client_buttons, self.text["save"].upper(), self._save_selected_client, CYBER["cyan"]).grid(row=0, column=1, padx=2, pady=2, sticky="ew")
        self._mini_button(client_buttons, self.text["delete"].upper(), self._delete_selected_client, CYBER["red"]).grid(row=0, column=2, padx=2, pady=2, sticky="ew")
        self._mini_button(client_buttons, self.text["use"].upper(), self._connect, CYBER["yellow"]).grid(row=0, column=3, padx=2, pady=2, sticky="ew")
        self._mini_button(client_buttons, self.text.get("clean", "Pulisci").upper(), self._clean_discovery_clients, CYBER["muted"]).grid(row=1, column=0, columnspan=4, padx=2, pady=(4, 2), sticky="ew")
        for col in range(4):
            client_buttons.columnconfigure(col, weight=1)

        move_pad = tk.Frame(content, bg=CYBER["panel"])
        move_pad.pack(fill="x", padx=16, pady=(0, 12))
        self._mini_button(move_pad, self.text["up"].upper(), lambda: self._move_selected(0, -1), CYBER["cyan"]).grid(row=0, column=1, padx=2, pady=2, sticky="ew")
        self._mini_button(move_pad, self.text["left"].upper(), lambda: self._move_selected(-1, 0), CYBER["cyan"]).grid(row=1, column=0, padx=2, pady=2, sticky="ew")
        self._mini_button(move_pad, self.text["right"].upper(), lambda: self._move_selected(1, 0), CYBER["cyan"]).grid(row=1, column=2, padx=2, pady=2, sticky="ew")
        self._mini_button(move_pad, self.text["down"].upper(), lambda: self._move_selected(0, 1), CYBER["cyan"]).grid(row=2, column=1, padx=2, pady=2, sticky="ew")
        for col in range(3):
            move_pad.columnconfigure(col, weight=1)

        tk.Label(content, text=self.text["clipboard"].upper(), fg=CYBER["cyan"], bg=CYBER["panel"], font=("Consolas", 12, "bold")).pack(anchor="w", padx=18, pady=(0, 6))
        clip = self.config.setdefault("clipboard", {})
        self.clipboard_enabled_var = tk.BooleanVar(value=bool(clip.get("enabled", False)))
        self.clipboard_files_var = tk.BooleanVar(value=bool(clip.get("files_enabled", False)))
        checks = tk.Frame(content, bg=CYBER["panel"])
        checks.pack(fill="x", padx=16, pady=(0, 8))
        self._check(checks, self.text["text"].upper(), self.clipboard_enabled_var, self._save_clipboard_config).pack(side="left", padx=(0, 8))
        self._check(checks, self.text["files"].upper(), self.clipboard_files_var, self._save_clipboard_config).pack(side="left")
        clip_buttons = tk.Frame(content, bg=CYBER["panel"])
        clip_buttons.pack(fill="x", padx=16, pady=(0, 12))
        self._mini_button(clip_buttons, self.text["send_text"].upper(), self._send_clipboard_text, CYBER["acid"]).grid(row=0, column=0, padx=2, pady=2, sticky="ew")
        self._mini_button(clip_buttons, self.text["get_text"].upper(), self._request_clipboard_text, CYBER["cyan"]).grid(row=0, column=1, padx=2, pady=2, sticky="ew")
        self._mini_button(clip_buttons, self.text["send_files"].upper(), self._send_clipboard_files, CYBER["yellow"]).grid(row=0, column=2, padx=2, pady=2, sticky="ew")
        for col in range(3):
            clip_buttons.columnconfigure(col, weight=1)

        tk.Label(content, text=self.text["advanced"].upper(), fg=CYBER["pink"], bg=CYBER["panel"], font=("Consolas", 12, "bold")).pack(anchor="w", padx=18, pady=(6, 6))
        advanced = tk.Frame(content, bg=CYBER["panel"])
        advanced.pack(fill="x", padx=16, pady=(0, 10))
        tk.Label(
            advanced,
            text=self.text["transparency"].upper(),
            fg=CYBER["muted"],
            bg=CYBER["panel"],
            font=("Consolas", 8, "bold"),
        ).grid(row=0, column=0, sticky="w", padx=(0, 8))
        self.opacity_var = tk.DoubleVar(value=round(self._ui_opacity() * 100))
        self.opacity_value = tk.Label(
            advanced,
            text=f"{int(self.opacity_var.get())}%",
            fg=CYBER["cyan"],
            bg=CYBER["panel"],
            font=("Consolas", 8, "bold"),
            width=5,
            anchor="e",
        )
        self.opacity_value.grid(row=0, column=2, sticky="e")
        opacity_scale = tk.Scale(
            advanced,
            from_=35,
            to=100,
            orient="horizontal",
            variable=self.opacity_var,
            command=self._opacity_changed,
            bg=CYBER["panel"],
            fg=CYBER["text"],
            troughcolor=CYBER["panel2"],
            activebackground=CYBER["cyan"],
            highlightthickness=0,
            bd=0,
            showvalue=False,
            resolution=1,
            length=180,
        )
        opacity_scale.grid(row=0, column=1, sticky="ew")
        opacity_scale.bind("<ButtonRelease-1>", self._save_ui_opacity)
        opacity_scale.bind("<KeyRelease>", self._save_ui_opacity)
        advanced.columnconfigure(1, weight=1)

        tk.Label(content, text=self.text["event_stream"].upper(), fg=CYBER["yellow"], bg=CYBER["panel"], font=("Consolas", 12, "bold")).pack(anchor="w", padx=18, pady=(6, 8))
        self.log = tk.Text(
            content,
            width=38,
            height=12,
            bg=CYBER["panel2"],
            fg=CYBER["text"],
            insertbackground=CYBER["cyan"],
            relief="flat",
            font=("Consolas", 9),
            borderwidth=0,
        )
        self.log.pack(fill="both", expand=True, padx=16, pady=(0, 16))
        if self.log_history:
            self.log.insert("end", "\n".join(self.log_history[-400:]) + "\n")
        self.log.see("end")
        self._refresh_client_list()

    def _control_center_geometry(self) -> str:
        width = 430
        height = 860
        try:
            self.root.update_idletasks()
            screen_x = int(self.root.winfo_vrootx())
            screen_y = int(self.root.winfo_vrooty())
            screen_w = int(self.root.winfo_vrootwidth())
            screen_h = int(self.root.winfo_vrootheight())
        except tk.TclError:
            screen_x = 0
            screen_y = 0
            screen_w = 1024
            screen_h = 768
        height = min(height, max(520, screen_h - 48))
        width = min(width, max(390, screen_w - 48))
        try:
            parent_x = int(self.root.winfo_rootx())
            parent_y = int(self.root.winfo_rooty())
            parent_w = max(1, int(self.root.winfo_width()))
            parent_h = max(1, int(self.root.winfo_height()))
        except tk.TclError:
            parent_x = screen_x
            parent_y = screen_y
            parent_w = screen_w
            parent_h = screen_h
        return centered_child_geometry(
            parent_x,
            parent_y,
            parent_w,
            parent_h,
            width,
            height,
            screen_x,
            screen_y,
            screen_w,
            screen_h,
        )

    def _close_control_center(self) -> None:
        window = getattr(self, "control_center", None)
        if window and window.winfo_exists():
            window.destroy()
        self.control_center = None
        for name in (
            "mode_box",
            "theme_box",
            "lang_box",
            "client_list",
            "client_name_var",
            "client_host_var",
            "client_port_var",
            "client_position_var",
            "position_box",
            "clipboard_enabled_var",
            "clipboard_files_var",
            "opacity_var",
            "opacity_value",
            "log",
        ):
            if hasattr(self, name):
                try:
                    delattr(self, name)
                except AttributeError:
                    pass

    def _refresh_main_client_picker(self) -> None:
        box = getattr(self, "main_client_box", None)
        if not box:
            return
        try:
            if not box.winfo_exists():
                return
        except tk.TclError:
            return
        values: list[str] = []
        lookup: dict[str, str] = {}
        selected_label = ""
        for client in self.config.get("clients", []):
            if not is_selectable_client(client):
                continue
            label = f"{client.get('name')} // {client.get('host')}:{client.get('port')}"
            key = client_key(client)
            values.append(label)
            lookup[label] = key
            if key == self.selected_client:
                selected_label = label
        self.main_client_lookup = lookup
        box.set_values(values)
        if selected_label:
            box.set(selected_label)
        elif values:
            box.set(values[0])
            self.selected_client = lookup[values[0]]

    def _select_client_from_picker(self, _event=None) -> None:
        if not hasattr(self, "main_client_var"):
            return
        lookup = getattr(self, "main_client_lookup", {})
        key = lookup.get(self.main_client_var.get())
        if not key:
            return
        self.selected_client = key
        client = self._client_config()
        self._configure_widget("client_badge", text=self._client_badge_text(client))
        self._refresh_client_list()
        self._draw_layout()

    def _client_config(self) -> dict:
        clients = self.config.setdefault("clients", [])
        if not clients:
            clients.append(normalize_client(DEFAULT_CONFIG["clients"][0]))
        for client in clients:
            if client_key(client) == self.selected_client and is_selectable_client(client):
                return client
        selectable = next((client for client in clients if is_selectable_client(client)), clients[0])
        self.selected_client = client_key(selectable)
        return selectable

    def _client_by_key(self, key: str) -> dict | None:
        return next((client for client in self.config.get("clients", []) if client_key(client) == key), None)

    def _active_client_config(self) -> dict | None:
        endpoint = getattr(self.link, "endpoint", None)
        if endpoint:
            host, port = endpoint
            key = f"{host}:{int(port)}"
            found = self._client_by_key(key)
            if found:
                return found
        return self._client_by_key(self.selected_client)

    def _next_client_from_edge(self, current: dict, edge: str) -> dict | None:
        cx, cy = client_grid(current)
        current_key = client_key(current)
        candidates: list[tuple[int, dict]] = []
        for client in self.config.get("clients", []):
            if client_key(client) == current_key or not is_selectable_client(client):
                continue
            x, y = client_grid(client)
            distance = 0
            if edge == "right" and y == cy and x > cx:
                distance = x - cx
            elif edge == "left" and y == cy and x < cx:
                distance = cx - x
            elif edge == "down" and x == cx and y > cy:
                distance = y - cy
            elif edge == "up" and x == cx and y < cy:
                distance = cy - y
            if distance:
                candidates.append((distance, client))
        if not candidates:
            return None
        return sorted(candidates, key=lambda item: item[0])[0][1]

    def _edge_points_toward_server(self, current: dict, edge: str) -> bool:
        x, y = client_grid(current)
        dx, dy = EDGE_DELTAS.get(edge, (0, 0))
        return abs(x + dx) + abs(y + dy) < abs(x) + abs(y)

    def _resolve_pending_client_endpoint(self, client: dict) -> bool:
        if not is_pending_client_host(str(client.get("host", ""))):
            return True
        name = str(client.get("name", "")).strip().lower()
        port = int(client.get("port", PORT))
        for key, item in self.discovered_clients.items():
            if not self._discovered_alive(key):
                continue
            if str(item.get("name", "")).strip().lower() == name and int(item.get("port", PORT)) == port:
                client["host"] = str(item.get("host", ""))
                client["port"] = port
                self._save_config()
                self._log(f"Client approvato risolto da discovery: {client.get('name')} {client.get('host')}:{port}")
                return True
        return False

    def _save_config(self) -> None:
        self.config["clients"] = normalize_layout_clients(list(self.config.get("clients", [])))
        (app_dir() / "config.json").write_text(json.dumps(self.config, indent=2), encoding="utf-8")

    def _apply_server_layout(self) -> None:
        self.config["clients"] = normalize_layout_clients(list(self.config.get("clients", [])))
        selected = self._client_by_key(self.selected_client)
        if not selected or not is_selectable_client(selected):
            self.selected_client = ""
            self._client_config()
        self._save_config()

    def _discovered_alive(self, key: str) -> bool:
        seen = float(self.discovered_clients.get(key, {}).get("seen", 0.0) or 0.0)
        return bool(seen and time.time() - seen <= DISCOVERY_CLIENT_TTL)

    def _active_discovery_count(self) -> int:
        now = time.time()
        return sum(1 for item in self.discovered_clients.values() if now - float(item.get("seen", 0.0) or 0.0) <= DISCOVERY_CLIENT_TTL)

    def _apply_client_health(self, payload: dict) -> None:
        key = str(payload.get("key", ""))
        if not key:
            key = f"{payload.get('host', '')}:{int(payload.get('port', PORT))}"
        payload = dict(payload)
        payload["key"] = key
        payload["seen"] = float(payload.get("seen", time.time()) or time.time())
        existing = getattr(self, "client_health", {}).get(key, {})
        existing_age = time.time() - float(existing.get("seen", 0.0) or 0.0)
        if (
            payload.get("state") == "offline"
            and existing.get("state") in {"online", "connected"}
            and existing_age <= CLIENT_HEALTH_OFFLINE_GRACE
        ):
            existing = dict(existing)
            existing["last_error"] = payload.get("detail", "")
            existing["last_probe_failed"] = payload["seen"]
            self.client_health[key] = existing
        else:
            self.client_health[key] = payload
        self._update_discovery_badge()
        self._refresh_client_list()
        self._draw_layout()

    def _mark_endpoint_health(self, endpoint: tuple[str, int] | None, state: str, source: str, detail: str = "", extra: dict | None = None) -> None:
        key = endpoint_key(endpoint)
        if not key:
            return
        if not hasattr(self, "client_health"):
            self.client_health = {}
        host, port = endpoint
        payload = {
            "key": key,
            "host": host,
            "port": int(port),
            "state": state,
            "source": source,
            "detail": detail,
            "seen": time.time(),
        }
        if extra:
            payload.update(extra)
        self.client_health[key] = payload

    def _client_runtime_view(self, client: dict) -> dict:
        key = client_key(client)
        source = str(client.get("source", "manual")).lower()
        if source == "discovery_pending" or not bool(client.get("enabled", True)):
            return {"state": "pending", "label": "PENDING", "color": CYBER["yellow"], "online": False, "connected": False}
        if is_pending_client_host(str(client.get("host", ""))):
            return {"state": "pending", "label": "PENDING IP", "color": CYBER["yellow"], "online": False, "connected": False}
        endpoint = client_endpoint(client)
        link = getattr(self, "link", None)
        if getattr(link, "connected", False) and getattr(link, "endpoint", None) == endpoint:
            return {"state": "connected", "label": self.text.get("connected_node", self.text["status_connected"]).upper(), "color": CYBER["acid"], "online": True, "connected": True}
        now = time.time()
        health = getattr(self, "client_health", {}).get(key, {})
        health_age = now - float(health.get("seen", 0.0) or 0.0)
        if health and health_age <= CLIENT_HEALTH_TTL:
            if health.get("state") in {"connected", "online"}:
                return {"state": "online", "label": self.text["online"].upper(), "color": CYBER["acid"], "online": True, "connected": False}
            if health.get("state") == "offline":
                return {"state": "offline", "label": self.text.get("offline", "Offline").upper(), "color": CYBER["red"], "online": False, "connected": False}
        if self._discovered_alive(key):
            return {"state": "online", "label": self.text["online"].upper(), "color": CYBER["acid"], "online": True, "connected": False}
        return {"state": "standby", "label": self.text["standby"].upper(), "color": CYBER["muted"], "online": False, "connected": False}

    def _client_health_summary(self) -> tuple[int, int, int]:
        selectable = [client for client in self.config.get("clients", []) if is_selectable_client(client) and not is_pending_client_host(str(client.get("host", "")))]
        online = sum(1 for client in selectable if self._client_runtime_view(client).get("online"))
        pending = sum(1 for client in self.config.get("clients", []) if not is_selectable_client(client) or is_pending_client_host(str(client.get("host", ""))))
        return online, len(selectable), pending

    def _set_client_inventory_badge(self, online: int, total: int, pending: int) -> None:
        badge = getattr(self, "discovery_badge", None)
        if not badge:
            return
        try:
            if not badge.winfo_exists():
                return
        except tk.TclError:
            return
        discovery = self._active_discovery_count()
        text = f"CLIENTI // {int(online)}/{int(total)} ONLINE // UDP {discovery}"
        if pending:
            text += f" // {int(pending)} PENDING"
        badge.configure(text=text)
        if getattr(self, "last_inventory_badge_text", "") != text:
            self.last_inventory_badge_text = text
            if hasattr(self, "_log") and hasattr(self, "log_history"):
                self._log(f"Health inventory: {text}")

    def _update_discovery_badge(self) -> None:
        badge = getattr(self, "discovery_badge", None)
        if not badge:
            return
        try:
            if not badge.winfo_exists():
                return
        except tk.TclError:
            return
        if not self.server_active:
            badge.configure(text=self.text["discovery_off"].upper())
            return
        if not self._discovery_enabled():
            badge.configure(text=self.text["discovery_disabled"].upper())
            return
        online, total, pending = self._client_health_summary()
        self._set_client_inventory_badge(online, total, pending)

    def _start_health_probe(self, *, force: bool = False) -> None:
        if not hasattr(self, "client_health"):
            self.client_health = {}
        if not self.server_active or getattr(self, "health_probe_running", False):
            return
        if getattr(getattr(self, "engine", None), "remote", False) and not force:
            return
        link = getattr(self, "link", None)
        if getattr(link, "connecting", False) and not force:
            return
        try:
            validate_token(self._token())
        except CryptoError:
            return
        clients = [
            dict(client)
            for client in self.config.get("clients", [])
            if is_selectable_client(client) and not is_pending_client_host(str(client.get("host", "")))
        ]
        if not clients:
            self._update_discovery_badge()
            return
        self.health_probe_running = True
        token = self._token()
        active_endpoint = getattr(link, "endpoint", None) if getattr(link, "connected", False) else None
        thread = threading.Thread(target=self._health_probe_thread, args=(clients, token, active_endpoint), daemon=True)
        thread.start()

    def _health_probe_thread(self, clients: list[dict], token: str, active_endpoint: tuple[str, int] | None) -> None:
        try:
            for client in clients:
                endpoint = client_endpoint(client)
                key = client_key(client)
                if endpoint == active_endpoint:
                    self.events.put(
                        (
                            "health",
                            {
                                "key": key,
                                "host": endpoint[0],
                                "port": endpoint[1],
                                "state": "connected",
                                "source": "link",
                                "detail": str(client.get("name", "")),
                                "seen": time.time(),
                            },
                        )
                    )
                    continue
                result = probe_secure_client(endpoint[0], endpoint[1], token)
                self.events.put(("health", result))
                time.sleep(0.05)
        finally:
            self.events.put(("health_probe_done", None))

    def _prune_transient_clients(self, startup: bool = False) -> bool:
        now = time.time()
        clients = []
        changed = False
        for client in self.config.get("clients", []):
            source = str(client.get("source", "manual")).lower()
            endpoint = (str(client.get("host", "")), int(client.get("port", PORT)))
            last_seen = float(client.get("last_seen", 0.0) or 0.0)
            remove = is_test_client(client)
            if source.startswith("discovery"):
                stale_saved = not last_seen or now - last_seen > DISCOVERY_CONFIG_TTL
                alive = self._discovered_alive(client_key(client))
                active_endpoint = getattr(getattr(self, "link", None), "endpoint", None)
                remove = remove or startup or (stale_saved and not alive and active_endpoint != endpoint)
            if remove:
                changed = True
                continue
            clients.append(client)

        if not changed:
            return False

        self.config["clients"] = clients
        if self.selected_client and not self._client_by_key(self.selected_client):
            self.selected_client = client_key(clients[0]) if clients else ""
        if hasattr(self, "client_list"):
            self._save_config()
            self._refresh_client_list()
            self._draw_layout()
        else:
            self.config["clients"] = [normalize_client(item, index) for index, item in enumerate(self.config.get("clients", []))]
            (app_dir() / "config.json").write_text(json.dumps(self.config, indent=2), encoding="utf-8")
        return True

    def _client_host(self) -> str:
        return str(self._client_config().get("host", "127.0.0.1"))

    def _client_port(self) -> int:
        return int(self._client_config().get("port", PORT))

    def _client_name(self) -> str:
        return str(self._client_config().get("name", "right-side-linux"))

    def _client_direction(self, client: dict | None = None) -> str:
        item = client or self._client_config()
        return position_from_grid(int(item.get("x", 1)), int(item.get("y", 0)))

    def _client_edges(self, client: dict | None = None) -> list[str]:
        item = client or self._client_config()
        try:
            x = int(item.get("x", 1))
            y = int(item.get("y", 0))
        except (TypeError, ValueError):
            x, y = 1, 0
        return client_edges_from_grid(x, y)

    def _direction_label(self, direction: str) -> str:
        return self.text.get(direction, direction).upper()

    def _client_badge_text(self, client: dict | None = None) -> str:
        item = client or self._client_config()
        direction = "/".join(self._direction_label(edge) for edge in self._client_edges(item))
        return f"{direction} // {item.get('name')} // {item.get('host')}:{item.get('port')}"

    def _toolbox_process_id(self) -> str:
        pid = os.getpid()
        parent = os.getppid() if hasattr(os, "getppid") else 0
        if parent and parent != pid:
            return f"{pid} / {parent}"
        return str(pid)

    def _token(self) -> str:
        return str(self.config.get("token") or DEFAULT_CONFIG["token"])

    def _token_valid(self) -> bool:
        try:
            validate_token(self._token())
            return True
        except CryptoError as exc:
            self._set_status(self.text["token_required"].upper(), CYBER["yellow"])
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

    def _pointer_inside_ui(self, x: int, y: int) -> bool:
        for window in (getattr(self, "root", None), getattr(self, "control_center", None)):
            if not window:
                continue
            try:
                if not window.winfo_exists() or not window.winfo_viewable():
                    continue
                rx = int(window.winfo_rootx())
                ry = int(window.winfo_rooty())
                rw = int(window.winfo_width())
                rh = int(window.winfo_height())
            except tk.TclError:
                continue
            if rx <= int(x) < rx + rw and ry <= int(y) < ry + rh:
                return True
        return False

    def _start_discovery(self) -> None:
        if not self.server_active:
            self._configure_widget("discovery_badge", text=self.text["discovery_off"].upper())
            return
        if self.discovery_beacon or self.discovery_listener:
            return
        if not self._discovery_enabled():
            self._log("Discovery LAN disattivata da configurazione.")
            self._configure_widget("discovery_badge", text=self.text["discovery_disabled"].upper())
            return
        token = self._token()
        try:
            validate_token(token)
        except CryptoError as exc:
            self._log(f"Discovery non avviata: {exc}")
            self._configure_widget("discovery_badge", text=self.text["discovery_token_required"].upper())
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
        self._configure_widget("discovery_badge", text=self.text["discovery_off"].upper())

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
        if is_test_client(name=name, host=host):
            return
        now = time.time()
        key = f"{host}:{port}"
        self.discovered_clients[key] = {"host": host, "port": port, "name": name, "seen": now}
        self._mark_endpoint_health((host, port), "online", "discovery", name, {"name": name})
        self._update_discovery_badge()
        clients = self.config.setdefault("clients", [])
        existing = next((client for client in clients if client_key(client) == key), None)
        claimed_pending = False
        if not existing:
            existing = pending_client_by_name(clients, name, port)
            claimed_pending = bool(existing)
        if existing:
            existing["name"] = name
            existing["host"] = host
            existing["port"] = port
            existing["last_seen"] = now
            existing["source"] = existing.get("source", "discovery")
            if claimed_pending:
                self._log(f"Client approvato rilevato: {name} {host}:{port}")
        elif len(clients) < MAX_CLIENTS:
            gx, gy = next_free_position(clients)
            auto_approve = bool(self.config.get("discovery", {}).get("auto_approve", False))
            source = "discovery" if auto_approve else "discovery_pending"
            clients.append(
                normalize_client(
                    {
                        "name": name,
                        "host": host,
                        "port": port,
                        "x": gx,
                        "y": gy,
                        "source": source,
                        "enabled": auto_approve,
                        "last_seen": now,
                    }
                )
            )
            if auto_approve:
                self._log(f"Client scoperto: {name} {host}:{port}")
            else:
                self._log(f"Client in attesa di approvazione: {name} {host}:{port}")
        self._save_config()
        self._refresh_client_list()
        self._draw_layout()
        if self._discovery_auto_connect() and not self.link.connected and not self.link.connecting:
            target = self._client_by_key(key)
            if target and target.get("enabled", True):
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

    def _configure_widget(self, name: str, **kwargs) -> bool:
        widget = getattr(self, name, None)
        if not widget:
            return False
        try:
            if not widget.winfo_exists():
                return False
            widget.configure(**kwargs)
            return True
        except tk.TclError:
            return False

    def _set_status(self, text: str, fg: str | None = None) -> None:
        options = {"text": text}
        if fg is not None:
            options["fg"] = fg
        self._configure_widget("status", **options)

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
        self._refresh_main_client_picker()
        self._configure_widget("client_badge", text=self._client_badge_text())
        widget = getattr(self, "client_list", None)
        if not widget or not widget.winfo_exists():
            return
        self.client_list.delete(0, "end")
        selected_index = 0
        for index, client in enumerate(self.config.get("clients", [])):
            key = client_key(client)
            marker = "*" if key == self.selected_client else " "
            state = self._client_runtime_view(client)["label"]
            self.client_list.insert(
                "end",
                f"{marker} {client.get('name')}  {client.get('host')}:{client.get('port')}  [{client.get('x')},{client.get('y')}]  {state}",
            )
            if key == self.selected_client:
                selected_index = index
        if self.config.get("clients"):
            self.client_list.selection_clear(0, "end")
            self.client_list.selection_set(selected_index)
            self.client_list.activate(selected_index)
            self._load_client_form(self._client_config())

    def _clean_discovery_clients(self) -> None:
        before = len(self.config.get("clients", []))
        self.discovered_clients = {
            key: value
            for key, value in self.discovered_clients.items()
            if time.time() - float(value.get("seen", 0.0) or 0.0) <= DISCOVERY_CLIENT_TTL
        }
        self.config["clients"] = [
            client
            for client in self.config.get("clients", [])
            if str(client.get("source", "manual")).lower() == "manual" and not is_test_client(client)
        ]
        if not self.config["clients"]:
            self.config["clients"] = [normalize_client(DEFAULT_CONFIG["clients"][0])]
        self.selected_client = client_key(self.config["clients"][0])
        self._save_config()
        self._refresh_client_list()
        self._update_discovery_badge()
        self._draw_layout()
        self._log(f"Pulizia discovery/offline: rimossi {max(0, before - len(self.config['clients']))} client.")

    def _refresh_now(self) -> None:
        current_key = self.selected_client
        try:
            self._apply_server_layout()
        except Exception as exc:
            self._log(f"Salvataggio layout fallito: {exc}")
            return
        try:
            self.config = load_config()
        except Exception as exc:
            self._log(f"Aggiornamento fallito: {exc}")
            return
        self.lang = self.config.get("language", "it") if self.config.get("language") in TEXT else "it"
        self.text = TEXT.get(self.lang, TEXT["it"])
        self.theme_id = self.config.get("theme", self.theme_id)
        CYBER.update(THEMES.get(self.theme_id, THEMES["old_school_x11"]))
        self.server_active = bool(self.config.get("server_on") and self.config.get("mode") == "server")
        self.engine.enabled = self.server_active
        if self.server_active:
            self._start_discovery()
        else:
            self._stop_discovery()
        selected = self._client_by_key(current_key)
        if selected and is_selectable_client(selected):
            self.selected_client = current_key
        else:
            self.selected_client = ""
            self._client_config()
        self._prune_transient_clients()
        self._refresh_server_toggle()
        self._refresh_client_list()
        self._update_discovery_badge()
        self._draw_layout()
        self.next_health_probe_ts = time.time() + CLIENT_HEALTH_PROBE_INTERVAL
        self._start_health_probe(force=True)
        if self.link.connected:
            self._set_status(self.text["status_connected"], "#39e58c")
        else:
            self._set_status(self.text["boot_ready"].upper(), CYBER["acid"])
        self._log("Aggiornato.")

    def _load_client_form(self, client: dict) -> None:
        if not all(hasattr(self, name) for name in ("client_name_var", "client_host_var", "client_port_var", "client_position_var")):
            return
        self.client_name_var.set(str(client.get("name", "")))
        self.client_host_var.set(str(client.get("host", "")))
        self.client_port_var.set(str(client.get("port", PORT)))
        self.client_position_var.set(position_label_from_grid(int(client.get("x", 1)), int(client.get("y", 0))))

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
        self._configure_widget("client_badge", text=self._client_badge_text(clients[index]))
        self._refresh_client_list()
        self._draw_layout()

    def _manual_form_client(self, base: dict | None = None) -> dict | None:
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
        label = self.client_position_var.get()
        if base and label == position_label_from_grid(int(base.get("x", 1)), int(base.get("y", 0))):
            gx = int(base.get("x", 1))
            gy = int(base.get("y", 0))
        else:
            gx, gy = grid_from_position(label)
        return normalize_client({"name": name, "host": host, "port": port, "x": gx, "y": gy, "source": "manual", "enabled": True})

    def _add_manual_client(self) -> None:
        client = self._manual_form_client()
        if not client:
            return
        clients = self.config.setdefault("clients", [])
        existing = next((item for item in clients if client_key(item) == client_key(client)), None)
        client = reserve_client_position(client, clients, client_key(existing) if existing else "")
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
        form = self._manual_form_client(selected)
        if not form:
            return
        form = reserve_client_position(form, self.config.get("clients", []), client_key(selected))
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

    def _set_pending_take(self, client: dict, direction: str, entry: dict | None, *, requires_edge: bool) -> None:
        self.pending_take_direction = direction
        self.pending_take_entry = dict(entry) if entry else None
        self.pending_take_client = client_key(client)
        self.pending_take_endpoint = (str(client.get("host", "")), int(client.get("port", PORT)))
        ttl = PENDING_EDGE_TAKE_TTL if requires_edge else PENDING_MANUAL_TAKE_TTL
        self.pending_take_deadline = time.monotonic() + ttl
        self.pending_take_requires_edge = requires_edge

    def _clear_pending_take(self) -> None:
        self.pending_take_direction = None
        self.pending_take_entry = None
        self.pending_take_client = ""
        self.pending_take_endpoint = None
        self.pending_take_deadline = 0.0
        self.pending_take_requires_edge = False

    def _consume_pending_take(self) -> tuple[str, dict | None] | None:
        direction = self.pending_take_direction
        entry = self.pending_take_entry
        pending_client = self.pending_take_client
        pending_endpoint = self.pending_take_endpoint
        requires_edge = self.pending_take_requires_edge
        deadline = self.pending_take_deadline
        self._clear_pending_take()
        if not direction or not self.server_active:
            return None
        if deadline and time.monotonic() > deadline:
            self._log("Take remoto annullato: richiesta bordo scaduta.")
            return None
        if pending_client and pending_client != self.selected_client:
            self._log("Take remoto annullato: client selezionato cambiato.")
            return None
        if pending_endpoint and self.link.endpoint != pending_endpoint:
            self._log("Take remoto annullato: endpoint connesso diverso dal client atteso.")
            return None
        if requires_edge:
            x, y = get_cursor()
            if self._pointer_inside_ui(x, y) or self.engine._host_edge(x, y) != direction:
                self._log("Take remoto annullato: il puntatore non e' piu' sul bordo.")
                return None
        return direction, entry

    def _connect_endpoint(self, endpoint: tuple[str, int], *, reason: str = "") -> None:
        current = getattr(self.link, "endpoint", None)
        if getattr(self.link, "connected", False) and current == endpoint:
            return
        if getattr(self.link, "connected", False):
            if reason:
                self._log(f"Cambio link remoto: {reason}.")
            self.link.disconnect()
        if not getattr(self.link, "connecting", False):
            self.link.connect(endpoint[0], endpoint[1], self._token(), self._identity())

    def _take_selected(self) -> None:
        client = self._client_config()
        direction = self._client_edges(client)[0]
        endpoint = (str(client.get("host")), int(client.get("port", PORT)))
        if not self.server_active:
            self._log("Server OFF: attiva SERVER ON prima di prendere controllo.")
            self._refresh_server_toggle()
            return
        if not is_selectable_client(client):
            self._log(f"Client {client.get('name')} non approvato o disabilitato.")
            return
        if is_pending_client_host(str(client.get("host", ""))):
            self._log(f"Client {client.get('name')} approvato ma IP ancora pending.")
            return
        if self.link.connected and self.link.endpoint == endpoint:
            self.engine.take(direction)
            return
        self._set_pending_take(client, direction, None, requires_edge=False)
        self._connect_endpoint(endpoint, reason=f"take {client.get('name')}")

    def _switch_remote_client(self, current: dict, target: dict, edge: str, payload: dict) -> bool:
        if not self._resolve_pending_client_endpoint(target):
            self._log(f"Client {target.get('name')} approvato ma IP ancora non risolto.")
            return False
        endpoint = (str(target.get("host")), int(target.get("port", PORT)))
        if is_pending_client_host(endpoint[0]):
            self._log(f"Client {target.get('name')} non raggiungibile: host ancora pending.")
            return False
        entry = edge_entry_from_client_payload(edge, payload, getattr(self.link, "client_info", {}))
        self._log(
            f"Routing remoto: {current.get('name')} bordo {edge} -> "
            f"{target.get('name')} {endpoint[0]}:{endpoint[1]}."
        )
        self.engine.release(restore_cursor=False)
        self.selected_client = client_key(target)
        self._set_pending_take(target, edge, entry, requires_edge=False)
        self._refresh_client_list()
        self._draw_layout()
        self._connect_endpoint(endpoint, reason=f"{current.get('name')} -> {target.get('name')}")
        return True

    def _handle_client_edge(self, edge: str, payload: dict) -> None:
        if not edge:
            return
        current = self._active_client_config()
        if not current:
            self.engine.client_edge(edge)
            return
        target = self._next_client_from_edge(current, edge)
        if target:
            self._switch_remote_client(current, target, edge, payload)
            return
        if self._edge_points_toward_server(current, edge):
            self._log(f"Rientro sul server da {current.get('name')} via bordo {edge}.")
            self.engine.release()
            return
        self._log(f"Nessun client adiacente a {current.get('name')} sul bordo {edge}.")

    def _fallback_route_client(self, direction: str) -> dict | None:
        return None

    def _route_from_edge(self, direction: str, entry: dict | None = None) -> bool:
        if not self.server_active:
            self.events.put(("log", "Server OFF: routing bordo disattivato."))
            return False
        candidates = [
            client
            for client in self.config.get("clients", [])
            if is_selectable_client(client) and direction in self._client_edges(client)
        ]
        target = (
            sorted(candidates, key=lambda item: abs(int(item.get("x", 0))) + abs(int(item.get("y", 0))))[0]
            if candidates
            else self._fallback_route_client(direction)
        )
        if not target:
            self.events.put(("log", f"Nessun client assegnato al bordo {direction}."))
            return False
        self.selected_client = client_key(target)
        self.events.put(("select", self.selected_client))
        endpoint = (str(target.get("host")), int(target.get("port", PORT)))
        if self.link.connected and self.link.endpoint == endpoint:
            return True
        self._set_pending_take(target, direction, entry, requires_edge=False)
        self._connect_endpoint(endpoint, reason=f"bordo {direction} -> {target.get('name')}")
        return False

    def _change_theme(self, _event=None) -> None:
        self.theme_id = THEME_VALUES.get(self.theme_box.get(), "old_school_x11")
        self.config["theme"] = self.theme_id
        CYBER.update(THEMES.get(self.theme_id, THEMES["old_school_x11"]))
        self._save_config()
        self._rebuild_ui()
        self._log(f"Tema impostato: {self.theme_id}. UI aggiornata.")
        self._draw_layout()

    def _rebuild_ui(self) -> None:
        self._close_control_center()
        self.client_boxes = {}
        self.drag_client = None
        for name in (
            "status",
            "server_toggle",
            "canvas",
            "client_badge",
            "discovery_badge",
            "signature_badge",
            "main_client_box",
            "main_client_var",
            "main_client_lookup",
        ):
            if hasattr(self, name):
                try:
                    delattr(self, name)
                except AttributeError:
                    pass
        for child in self.root.winfo_children():
            child.destroy()
        self.root.configure(bg=CYBER["bg"])
        min_w, min_h = self._surface_minsize()
        self.root.minsize(min_w, min_h)
        self._style()
        self._build()

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
        button = getattr(self, "server_toggle", None)
        if not button:
            return
        if self.server_active:
            try:
                if not button.winfo_exists():
                    return
            except tk.TclError:
                return
            button.configure(
                text="TORNA TOOLBOX",
                fg=CYBER["acid"],
                activebackground=CYBER["red"],
                highlightbackground=CYBER["acid"],
                highlightcolor=CYBER["acid"],
            )
            self._set_status(self.text["server_on"].upper(), CYBER["acid"])
        else:
            try:
                if not button.winfo_exists():
                    return
            except tk.TclError:
                return
            button.configure(
                text="DIVENTA SERVER",
                fg=CYBER["acid"],
                activebackground=CYBER["acid"],
                highlightbackground=CYBER["acid"],
                highlightcolor=CYBER["acid"],
            )
            if not self.link.connected:
                self._set_status(self.text["client_mode_route"].upper(), CYBER["yellow"])

    def _set_server_active(self, active: bool) -> None:
        surface_changed = bool(self.server_active) != bool(active)
        if active:
            self.config["mode"] = "server"
            self.config["server_on"] = True
            if hasattr(self, "mode_box"):
                self.mode_box.set(MODE_LABELS["server"])
            if not self._token_valid():
                self.config["mode"] = "client"
                self.config["server_on"] = False
                self.server_active = False
                self.engine.enabled = False
                self._save_config()
                if surface_changed:
                    self.root.geometry(self._startup_geometry())
                    self._rebuild_ui()
                else:
                    self._refresh_server_toggle()
                return
            self.server_active = True
            self.engine.enabled = True
            self._save_config()
            if surface_changed:
                self.root.geometry(self._startup_geometry())
                self._rebuild_ui()
            else:
                self._refresh_server_toggle()
            self._start_discovery()
            self._auto_connect()
            self._log("Server ON: discovery, connessione client e routing bordo attivi.")
            return

        if self.engine.remote:
            self.engine.release()
        self._clear_pending_take()
        self.server_active = False
        self.engine.enabled = False
        self.config["mode"] = "client"
        self.config["server_on"] = False
        if hasattr(self, "mode_box"):
            self.mode_box.set(MODE_LABELS["client"])
        self.link.disconnect()
        self._stop_discovery()
        self._save_config()
        if surface_changed:
            self.root.geometry(self._startup_geometry())
            self._rebuild_ui()
        else:
            self._refresh_server_toggle()

    def _layout_metrics(self, w: int, h: int) -> tuple[int, int, float, float, int, int]:
        clients = self.config.get("clients", [])
        xs = [0] + [int(client.get("x", 0)) for client in clients]
        ys = [0] + [int(client.get("y", 0)) for client in clients]
        node_w = max(210, min(260, int(w * 0.24)))
        node_h = max(112, min(138, int(h * 0.18)))
        margin_x = 36
        margin_y = 42
        max_abs_x = max(1, max(abs(value) for value in xs))
        max_abs_y = max(1, max(abs(value) for value in ys))
        available_x = max(120.0, (w / 2) - (node_w / 2) - margin_x)
        available_y = max(96.0, (h / 2) - (node_h / 2) - margin_y)
        cell_w = max(50.0, min(360.0, available_x / max_abs_x))
        cell_h = max(45.0, min(260.0, available_y / max_abs_y))
        center_x = w // 2
        center_y = h // 2
        return center_x, center_y, cell_w, cell_h, node_w, node_h

    def _point_to_grid(self, x: int, y: int) -> tuple[int, int]:
        w = max(420, self.canvas.winfo_width())
        h = max(320, self.canvas.winfo_height())
        center_x, center_y, cell_w, cell_h, _node_w, _node_h = self._layout_metrics(w, h)
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
        self.tray_icon = pystray.Icon(
            "KyMoRem",
            image,
            "KyMoRem // Edge Router",
            self._tray_menu(),
        )
        self.tray_icon.run_detached()
        self._log("Tray Windows attiva.")

    def _tray_menu(self):
        return pystray.Menu(
            pystray.MenuItem(self.text["open_app"], lambda _icon, _item: self.root.after(0, self._show_window)),
            pystray.MenuItem("Server ON/OFF", lambda _icon, _item: self.root.after(0, self._toggle_server)),
            pystray.MenuItem(self.text["connect"], lambda _icon, _item: self.root.after(0, self._connect)),
            pystray.MenuItem(self.text["take"], lambda _icon, _item: self.root.after(0, self._take_selected)),
            pystray.MenuItem(self.text["release"], lambda _icon, _item: self.root.after(0, self.engine.release)),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem(self.text["exit"], lambda _icon, _item: self.root.after(0, self._quit)),
        )

    def _refresh_tray_menu(self) -> None:
        if not self.tray_icon or pystray is None:
            return
        try:
            self.tray_icon.menu = self._tray_menu()
            self.tray_icon.update_menu()
        except Exception:
            pass

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
        c = getattr(self, "canvas", None)
        if not c:
            return
        c.delete("all")
        w = max(420, c.winfo_width())
        h = max(320, c.winfo_height())
        c.create_rectangle(0, 0, w, h, fill=CYBER["bg2"], outline="")
        self._draw_cyber_grid(w, h)
        c.create_text(
            w // 2,
            h // 2,
            text=APP_NAME,
            fill=CYBER["line"],
            font=("Consolas", max(32, min(96, w // 9)), "bold"),
            anchor="center",
        )
        c.create_text(
            w // 2,
            h // 2 + max(36, min(78, w // 18)),
            text=APP_EXTENDED_NAME.upper(),
            fill=CYBER["muted"],
            font=("Consolas", max(9, min(15, w // 90)), "bold"),
            anchor="center",
        )

        self.client_boxes = {}
        clients = self.config.get("clients", [])
        center_x, center_y, cell_w, cell_h, node_w, node_h = self._layout_metrics(w, h)
        server = (center_x - node_w // 2, center_y - node_h // 2, center_x + node_w // 2, center_y + node_h // 2)
        server_state = self.text["server_on"].upper() if self.server_active else self.text["client_mode"].upper()
        server_pill = self.text.get("active", "Attivo").upper() if self.server_active else self.text.get("offline", "Offline").upper()
        self._node_card(
            server,
            "SERVER",
            server_state,
            CYBER["cyan"],
            active=self.server_active and not self.engine.remote,
            state_label=server_pill,
            state_color=CYBER["acid"] if self.server_active else CYBER["red"],
        )
        self._portal(center_x, center_y, CYBER["cyan"])

        selected = self._client_config()
        selected_key = client_key(selected)
        link_color = CYBER["acid"] if self.link.connected else CYBER["line"]
        layout_online = 0
        layout_total = 0
        layout_pending = 0
        for client in clients:
            gx = int(client.get("x", 1))
            gy = int(client.get("y", 0))
            cx = int(max(node_w // 2 + 18, min(w - node_w // 2 - 18, center_x + gx * cell_w)))
            cy = int(max(node_h // 2 + 18, min(h - node_h // 2 - 18, center_y + gy * cell_h)))
            box = (cx - node_w // 2, cy - node_h // 2, cx + node_w // 2, cy + node_h // 2)
            key = client_key(client)
            self.client_boxes[key] = box
            view = self._client_runtime_view(client)
            if is_selectable_client(client) and not is_pending_client_host(str(client.get("host", ""))):
                layout_total += 1
                if view.get("online"):
                    layout_online += 1
            else:
                layout_pending += 1
            active = bool(view.get("connected"))
            color = CYBER["pink"] if key == selected_key else CYBER["cyan"]
            if active:
                color = CYBER["acid"]
            elif view.get("online"):
                color = CYBER["acid"]
            elif view.get("state") == "offline":
                color = CYBER["red"]
            c.create_line(center_x, center_y, cx, cy, fill=CYBER["cyan_dim"] if view.get("online") else CYBER["line"], width=2)
            self._node_card(
                box,
                str(client.get("name", "client")).upper()[:18],
                f"{client.get('host')}:{client.get('port')} // {'/'.join(self._client_edges(client))}",
                color,
                active=bool(view.get("online")),
                state_label=str(view.get("label", self.text["standby"].upper())),
                state_color=str(view.get("color", CYBER["muted"])),
            )
        if self.server_active and self._discovery_enabled():
            self._set_client_inventory_badge(layout_online, layout_total, layout_pending)

        if not self.server_active:
            route_text = self.text["client_mode_route"].upper()
        else:
            route_text = self.text["link_online_route"].upper() if self.link.connected else self.text["link_offline_route"].upper()
        if self.engine.remote:
            route_text = self.text["remote_route"].upper()
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
            text=f"{self.local_ip}  >>>  {self._client_host()}:{self._client_port()} // {self.text['selected']} {'/'.join(self._client_edges())}",
            fill=CYBER["muted"],
            font=("Consolas", 10),
        )

    def _draw_cyber_grid(self, w: int, h: int) -> None:
        c = self.canvas
        c.create_rectangle(18, 18, w - 18, h - 18, outline=CYBER["line"], width=1)
        c.create_text(w - 28, 32, text=self.text["client_layout"], anchor="e", fill=CYBER["muted"], font=("Consolas", 10, "bold"))
        c.create_text(28, 32, text=self.text["routing_map"], anchor="w", fill=CYBER["muted"], font=("Consolas", 10, "bold"))

    def _beveled_rect(self, box: tuple[int, int, int, int], outline: str, fill: str) -> None:
        x1, y1, x2, y2 = box
        self.canvas.create_rectangle(x1, y1, x2, y2, fill=fill, outline=outline, width=2)

    def _node_card(
        self,
        box: tuple[int, int, int, int],
        title: str,
        subtitle: str,
        color: str,
        active: bool,
        state_label: str | None = None,
        state_color: str | None = None,
    ) -> None:
        x1, y1, x2, y2 = box
        c = self.canvas
        self._beveled_rect(box, color, CYBER["panel"])
        c.create_text(x1 + 16, y1 + 22, text=title, anchor="w", fill=color, font=("Consolas", 14, "bold"))
        c.create_text(x1 + 16, y1 + 50, text=subtitle[:32], anchor="w", fill=CYBER["text"], font=("Consolas", 9, "bold"))
        state = state_label or (self.text["online"].upper() if active else self.text["standby"].upper())
        pill = state_color or (CYBER["acid"] if active else CYBER["muted"])
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
        client = self._client_config()
        if not is_selectable_client(client):
            self._log(f"Client {client.get('name')} non approvato o disabilitato.")
            return
        if is_pending_client_host(str(client.get("host", ""))):
            self._log(f"Client {client.get('name')} approvato ma IP ancora pending.")
            return
        self._configure_widget("client_badge", text=self._client_badge_text(client))
        endpoint = (str(client.get("host")), int(client.get("port", PORT)))
        self._connect_endpoint(endpoint, reason=f"selezione {client.get('name')}")

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
        self.text = TEXT.get(self.lang, TEXT["it"])
        self._save_config()
        self._refresh_tray_menu()
        self._rebuild_ui()
        self._log(self.text["language_set"].format(label=LANG_LABELS.get(self.lang, self.lang)))
        self._draw_layout()

    def _show_pointer_hint(self, payload: dict) -> None:
        self.pointer_hint = payload
        self.pointer_hint_until = time.monotonic() + 4.0
        scope = str(payload.get("scope", "server")).upper()
        x = payload.get("x")
        y = payload.get("y")
        screen = payload.get("screen", "")
        self._set_status(f"POINTER {scope} X={x} Y={y}", CYBER["yellow"])
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
            elif kind == "health":
                self._apply_client_health(payload)
            elif kind == "health_probe_done":
                self.health_probe_running = False
            elif kind == "remote":
                self._set_status(self.text["remote"].upper() if payload else self.text["status_connected"])
                self._draw_layout()
            elif kind == "pointer":
                self._show_pointer_hint(payload)
            elif kind == "select":
                self.selected_client = str(payload)
                self._refresh_client_list()
                self._draw_layout()
            elif kind == "disconnected":
                self._clear_pending_take()
                if self.engine.remote:
                    self.engine.release()
                else:
                    self.engine._show_host_cursor(force=True)
                self._update_discovery_badge()
                if self.server_active:
                    self._set_status(self.text["status_disconnected"], "#ff5c7a")
                else:
                    self._set_status(self.text["client_mode_route"].upper(), CYBER["yellow"])
                self._draw_layout()
        now = time.time()
        if now >= self.next_prune_ts:
            self.next_prune_ts = now + 5.0
            self._prune_transient_clients()
            self._update_discovery_badge()
            self._draw_layout()
        if self.server_active and now >= self.next_health_probe_ts:
            self.next_health_probe_ts = now + CLIENT_HEALTH_PROBE_INTERVAL
            self._start_health_probe()
        self.root.after(80, self._tick)

    def _handle_frame(self, message: dict) -> None:
        kind = message.get("type")
        payload = message.get("payload", {})
        if kind == "hello":
            self.link.client_info = dict(payload)
            self._mark_endpoint_health(self.link.endpoint, "connected", "link", str(payload.get("name", "")), dict(payload))
            self._update_discovery_badge()
            self._set_status(self.text["status_connected"], "#39e58c")
            self._log(f"Client: {payload.get('name')} {payload.get('width')}x{payload.get('height')}")
            pending = self._consume_pending_take()
            if pending:
                direction, entry = pending
                self.root.after(120, lambda d=direction, e=entry: self.engine.take(d, e))
            self._draw_layout()
        elif kind == "edge":
            edge = str(payload.get("edge", ""))
            now = time.monotonic()
            if edge:
                last = float(self.last_client_edge_log.get(edge, 0.0))
                if now - last >= 0.35:
                    self.last_client_edge_log[edge] = now
                    self._log(f"Il client ha raggiunto il bordo {edge}: valuto ritorno/routing.")
            self._handle_client_edge(edge, payload)
        elif kind == "pulse_ack":
            self._log("Pulse OK dal client.")
        elif kind == "keepalive_ack":
            self.link.client_info.update(payload)
            self.engine.note_keepalive_ack()
        elif kind == "pointer_position":
            self.link.client_info.update(payload)
            payload["scope"] = payload.get("name", "client")
            self._show_pointer_hint(payload)
        elif kind == "entered":
            self.link.client_info.update(payload)
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
        self.log_history.append(line)
        if len(self.log_history) > 400:
            self.log_history = self.log_history[-400:]
        widget = getattr(self, "log", None)
        if widget:
            try:
                if widget.winfo_exists():
                    widget.insert("end", line + "\n")
                    widget.see("end")
            except tk.TclError:
                pass
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
