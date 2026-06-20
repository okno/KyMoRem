import ctypes
import json
import os
import queue
import smtplib
import socket
import sys
import threading
import time
import tkinter as tk
from email.message import EmailMessage
from pathlib import Path
from tkinter import ttk

from kymorem_common import APP_NAME, DEFAULT_CONFIG, PORT, TEXT, VERSION, frame
from kymorem_crypto import CryptoError, secure_connect
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
    "VK_LWIN": 0x5B,
    "VK_RWIN": 0x5C,
    **{f"VK_{chr(code)}": code for code in range(ord("A"), ord("Z") + 1)},
    **{f"VK_{n}": 0x30 + n for n in range(10)},
}

BUTTON_KEYS = {
    "left": VK["VK_LBUTTON"],
    "right": VK["VK_RBUTTON"],
    "middle": VK["VK_MBUTTON"],
}

KEY_SCAN = {name: code for name, code in VK.items() if name not in {"VK_LBUTTON", "VK_RBUTTON", "VK_MBUTTON"}}


class POINT(ctypes.Structure):
    _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]


user32 = ctypes.windll.user32

CYBER = {
    "bg": "#04060c",
    "bg2": "#070b16",
    "panel": "#0b1020",
    "panel2": "#11162a",
    "line": "#1c2b46",
    "text": "#f7fbff",
    "muted": "#8ea4c8",
    "cyan": "#00f5ff",
    "cyan_dim": "#0b778c",
    "pink": "#ff2bd6",
    "pink_dim": "#7b1f68",
    "acid": "#b7ff2a",
    "yellow": "#ffe45e",
    "red": "#ff3864",
}


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


def local_ip_hint() -> str:
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.connect(("8.8.8.8", 80))
            return sock.getsockname()[0]
    except OSError:
        return "local-host"


def app_dir() -> Path:
    base = os.environ.get("APPDATA") or str(Path.home())
    path = Path(base) / "KyMoRem"
    path.mkdir(parents=True, exist_ok=True)
    return path


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
    for key in ["security", "discovery", "email_relay"]:
        merged = dict(DEFAULT_CONFIG[key])
        merged.update(config.get(key, {}))
        if merged != config.get(key):
            config[key] = merged
            changed = True
    if config.get("language") not in TEXT:
        config["language"] = "ch"
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
        self.connected = False
        self.connecting = False
        self.client_info: dict = {}

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
            secure.send(frame(kind, **payload))
        except Exception as exc:
            self.events.put(("log", f"Invio fallito: {exc}"))
            self.disconnect()


class ControlEngine:
    def __init__(self, link: RemoteLink, events: queue.Queue):
        self.link = link
        self.events = events
        self.remote = False
        self.running = True
        self.w, self.h = screen_size()
        self.anchor = (self.w // 2, self.h // 2)
        self.button_state = {name: False for name in BUTTON_KEYS}
        self.key_state = {name: False for name in KEY_SCAN}
        self.thread = threading.Thread(target=self.loop, daemon=True)
        self.thread.start()

    def take(self) -> None:
        if not self.link.connected:
            self.events.put(("log", "Nessun client connesso."))
            return
        self.remote = True
        set_cursor(*self.anchor)
        self.events.put(("remote", True))
        self.events.put(("log", "Controllo remoto attivo. Ctrl+Esc rilascia."))

    def release(self) -> None:
        if self.remote:
            self.remote = False
            set_cursor(self.w - 3, self.h // 2)
            self.link.send("release")
            self.events.put(("remote", False))
            self.events.put(("log", "Controllo remoto rilasciato."))

    def edge_left(self) -> None:
        self.release()

    def loop(self) -> None:
        while self.running:
            time.sleep(0.012)
            if not self.remote:
                if self.link.connected:
                    x, _ = get_cursor()
                    if x >= self.w - 2:
                        self.take()
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

            for button, vk in BUTTON_KEYS.items():
                down = async_down(vk)
                if down != self.button_state[button]:
                    self.button_state[button] = down
                    self.link.send("button", button=button, state="down" if down else "up")

            for key, vk in KEY_SCAN.items():
                down = async_down(vk)
                if down != self.key_state[key]:
                    self.key_state[key] = down
                    self.link.send("key", key=key, state="down" if down else "up")


class KyMoRemApp:
    def __init__(self) -> None:
        self.config = load_config()
        self.lang = self.config.get("language", "it")
        self.text = TEXT.get(self.lang, TEXT["it"])
        self.local_ip = local_ip_hint()
        self.discovered_clients: dict[str, dict] = {}
        self.events: queue.Queue = queue.Queue()
        self.link = RemoteLink(self.events)
        self.engine = ControlEngine(self.link, self.events)
        self.discovery_beacon = None
        self.discovery_listener = None
        self.tray_icon = None
        self.root = tk.Tk()
        self.root.title(f"{APP_NAME} {VERSION} // Neon Route Console")
        self.root.geometry("1120x700")
        self.root.minsize(980, 620)
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
        self._start_discovery()
        self._start_tray()
        self._tick()
        self._auto_connect()

    def _style(self) -> None:
        style = ttk.Style()
        style.theme_use("clam")
        style.configure(
            "TCombobox",
            fieldbackground=CYBER["panel"],
            background=CYBER["panel"],
            foreground=CYBER["text"],
            bordercolor=CYBER["cyan"],
            arrowcolor=CYBER["cyan"],
            selectbackground=CYBER["pink_dim"],
            selectforeground=CYBER["text"],
        )

    def _build(self) -> None:
        header = tk.Frame(self.root, bg=CYBER["bg"])
        header.pack(fill="x", padx=24, pady=(18, 10))

        title_box = tk.Frame(header, bg=CYBER["bg"])
        title_box.pack(side="left", fill="x", expand=True)
        tk.Label(
            title_box,
            text="KYMOREM",
            fg=CYBER["cyan"],
            bg=CYBER["bg"],
            font=("Consolas", 34, "bold"),
        ).pack(anchor="w")
        tk.Label(
            title_box,
            text="KEYBOARD MOUSE REMOTE // RIGHT EDGE ROUTER // LAN NODE 54865",
            fg=CYBER["pink"],
            bg=CYBER["bg"],
            font=("Consolas", 11, "bold"),
        ).pack(anchor="w", pady=(0, 2))

        self.lang_box = ttk.Combobox(header, values=["it", "en", "ch"], width=5, state="readonly")
        self.lang_box.set(self.lang)
        self.lang_box.bind("<<ComboboxSelected>>", self._change_lang)
        self.lang_box.pack(side="right", pady=(20, 0))

        body = tk.Frame(self.root, bg=CYBER["bg"])
        body.pack(fill="both", expand=True, padx=24, pady=10)

        left = tk.Frame(body, bg=CYBER["bg"])
        left.pack(side="left", fill="both", expand=True)

        right = tk.Frame(body, bg=CYBER["panel"], bd=0, highlightthickness=2, highlightbackground=CYBER["pink"])
        right.pack(side="right", fill="y", padx=(18, 0))

        self.canvas = tk.Canvas(left, bg=CYBER["bg2"], highlightthickness=2, highlightbackground=CYBER["cyan"])
        self.canvas.pack(fill="both", expand=True)
        self.canvas.bind("<Configure>", lambda _event: self._draw_layout())

        controls = tk.Frame(left, bg=CYBER["bg"])
        controls.pack(fill="x", pady=(14, 0))
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
            bg=CYBER["bg"],
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
            text="DISCOVERY // ARMED",
            fg=CYBER["muted"],
            bg=CYBER["panel"],
            font=("Consolas", 9, "bold"),
        )
        self.discovery_badge.pack(anchor="w", padx=18, pady=(0, 12))

        tk.Label(right, text="EVENT STREAM", fg=CYBER["yellow"], bg=CYBER["panel"], font=("Consolas", 12, "bold")).pack(anchor="w", padx=18, pady=(6, 8))
        self.log = tk.Text(
            right,
            width=38,
            height=24,
            bg="#03050a",
            fg=CYBER["muted"],
            insertbackground=CYBER["cyan"],
            relief="flat",
            font=("Consolas", 9),
            borderwidth=0,
        )
        self.log.pack(fill="both", expand=True, padx=16, pady=(0, 16))

        tk.Label(
            self.root,
            text="CONTROL VECTOR: push cursor through RIGHT EDGE // EMERGENCY RELEASE: Ctrl+Esc",
            fg=CYBER["muted"],
            bg=CYBER["bg"],
            font=("Consolas", 10),
        ).pack(anchor="w", padx=24, pady=(0, 16))
        self._draw_layout()

    def _client_config(self) -> dict:
        return self.config.get("clients", [{}])[0]

    def _client_host(self) -> str:
        return str(self._client_config().get("host", "127.0.0.1"))

    def _client_port(self) -> int:
        return int(self._client_config().get("port", PORT))

    def _client_name(self) -> str:
        return str(self._client_config().get("name", "right-side-linux"))

    def _token(self) -> str:
        return str(self.config.get("token") or DEFAULT_CONFIG["token"])

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
        message["From"] = str(relay.get("from"))
        message["To"] = ", ".join(relay.get("to", []))
        message["Subject"] = subject
        message.set_content(body + f"\n\nHost: {self.local_ip}\nVersion: {VERSION}\n")
        password = os.environ.get(str(relay.get("smtp_password_env", "KYMOREM_SMTP_PASSWORD")), "")
        try:
            with smtplib.SMTP(str(relay.get("smtp_host")), int(relay.get("smtp_port", 587)), timeout=10) as smtp:
                if relay.get("smtp_starttls", True):
                    smtp.starttls()
                username = str(relay.get("smtp_username", ""))
                if username:
                    smtp.login(username, password)
                smtp.send_message(message)
        except Exception as exc:
            self.events.put(("log", f"Email relay fallito: {exc}"))

    def _start_discovery(self) -> None:
        if not self._discovery_enabled():
            self._log("Discovery LAN disattivata da configurazione.")
            return
        token = self._token()
        name = str(self.config.get("server_name") or os.environ.get("COMPUTERNAME", "Windows"))
        self.discovery_beacon = DiscoveryBeacon(token, "host", name, PORT)
        self.discovery_listener = DiscoveryListener(token, lambda payload, addr: self.events.put(("discovery", (payload, addr))))
        self.discovery_beacon.start()
        self.discovery_listener.start()
        self._log("Discovery LAN cifrata attiva su UDP 54866.")

    def _handle_discovery(self, event) -> None:
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
        if self._discovery_auto_connect() and not self.link.connected and not self.link.connecting:
            client = self._client_config()
            if client.get("host") in {"", "127.0.0.1", DEFAULT_CONFIG["clients"][0]["host"]}:
                client["host"] = host
                client["port"] = port
                client["name"] = name
                self.client_badge.configure(text=f"RIGHT NODE // {host}")
                self._log(f"Client scoperto: {name} {host}:{port}")
                self._connect()

    def _neon_button(self, parent, text: str, command, accent: str) -> tk.Button:
        return tk.Button(
            parent,
            text=text.upper(),
            command=command,
            bg=CYBER["panel"],
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
        self.engine.running = False
        if self.discovery_beacon:
            self.discovery_beacon.close()
        if self.discovery_listener:
            self.discovery_listener.close()
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
        w = max(760, c.winfo_width())
        h = max(430, c.winfo_height())
        c.create_rectangle(0, 0, w, h, fill=CYBER["bg2"], outline="")
        self._draw_cyber_grid(w, h)

        server = (58, 82, min(360, w // 2 - 80), 292)
        client = (max(430, w // 2 + 70), 82, min(w - 58, w // 2 + 392), 292)
        link_color = CYBER["acid"] if self.link.connected else CYBER["line"]
        remote_color = CYBER["pink"] if self.engine.remote else CYBER["cyan"]

        self._node_card(server, "HOST CORE", "WINDOWS // LOCAL INPUT", CYBER["cyan"], active=not self.engine.remote)
        self._node_card(
            client,
            "REMOTE NODE",
            f"{self._client_name().upper()} // {self._client_host()}",
            remote_color if self.link.connected else CYBER["line"],
            active=self.engine.remote,
        )

        sx = server[2]
        sy = (server[1] + server[3]) // 2
        cx = client[0]
        cy = (client[1] + client[3]) // 2
        for width, color in [(10, "#07111a"), (6, CYBER["cyan_dim"]), (3, link_color)]:
            c.create_line(sx, sy, w // 2 - 52, sy, w // 2 + 52, cy, cx, cy, fill=color, width=width)
        c.create_polygon(cx - 18, cy - 11, cx + 2, cy, cx - 18, cy + 11, fill=link_color, outline="")

        self._portal(server[2] - 10, sy, CYBER["cyan"])
        self._portal(client[0] + 10, cy, remote_color if self.link.connected else CYBER["line"])

        route_text = "LINK ONLINE // RIGHT EDGE ARMED" if self.link.connected else "LINK OFFLINE // WAITING FOR NODE"
        if self.engine.remote:
            route_text = "REMOTE CONTROL ACTIVE // RETURN VIA LEFT EDGE"
        c.create_text(w // 2, 332, text=route_text, fill=link_color if self.link.connected else CYBER["muted"], font=("Consolas", 13, "bold"))
        c.create_text(
            w // 2,
            360,
            text=f"{self.local_ip}  >>>  {self._client_host()}:{self._client_port()}",
            fill=CYBER["muted"],
            font=("Consolas", 10),
        )

        self._scanlines(w, h)

    def _draw_cyber_grid(self, w: int, h: int) -> None:
        c = self.canvas
        horizon = int(h * 0.68)
        for y in range(horizon, h, 18):
            alpha = min(1.0, (y - horizon + 20) / max(1, h - horizon))
            color = CYBER["cyan_dim"] if alpha > 0.45 else CYBER["line"]
            c.create_line(0, y, w, y, fill=color)
        center = w // 2
        for offset in range(-w, w + 1, 58):
            c.create_line(center, horizon, center + offset, h, fill=CYBER["line"])
        for x in range(0, w, 74):
            c.create_line(x, 0, x, horizon, fill="#0b1424")
        c.create_text(w - 22, 24, text="NEON ROUTE MAP", anchor="e", fill=CYBER["pink"], font=("Consolas", 10, "bold"))
        c.create_text(22, 24, text="GRID//ACTIVE", anchor="w", fill=CYBER["cyan"], font=("Consolas", 10, "bold"))

    def _beveled_rect(self, box: tuple[int, int, int, int], outline: str, fill: str) -> None:
        x1, y1, x2, y2 = box
        cut = 20
        points = [
            x1 + cut, y1,
            x2, y1,
            x2, y2 - cut,
            x2 - cut, y2,
            x1, y2,
            x1, y1 + cut,
        ]
        self.canvas.create_polygon(points, fill=fill, outline=outline, width=2)
        self.canvas.create_line(x1 + cut, y1 + 5, x2 - 28, y1 + 5, fill=outline, width=1)
        self.canvas.create_line(x1 + 5, y1 + cut, x1 + 5, y2 - 26, fill=outline, width=1)

    def _node_card(self, box: tuple[int, int, int, int], title: str, subtitle: str, color: str, active: bool) -> None:
        x1, y1, x2, y2 = box
        c = self.canvas
        self._beveled_rect(box, color, CYBER["panel"])
        c.create_rectangle(x1 + 24, y1 + 38, x2 - 24, y1 + 120, fill="#03050a", outline=CYBER["line"])
        c.create_text(x1 + 30, y1 + 28, text=title, anchor="w", fill=color, font=("Consolas", 15, "bold"))
        c.create_text(x1 + 30, y2 - 52, text=subtitle, anchor="w", fill=CYBER["text"], font=("Consolas", 10, "bold"))
        c.create_text(x1 + 30, y2 - 28, text="ONLINE" if active else "STANDBY", anchor="w", fill=CYBER["acid"] if active else CYBER["muted"], font=("Consolas", 9, "bold"))
        for i in range(5):
            y = y1 + 56 + i * 12
            c.create_line(x1 + 42, y, x2 - 48 - i * 18, y, fill=color if i % 2 == 0 else CYBER["line"], width=2)
        c.create_oval(x2 - 74, y1 + 54, x2 - 36, y1 + 92, outline=color, width=3)
        c.create_oval(x2 - 64, y1 + 64, x2 - 46, y1 + 82, outline=CYBER["text"] if active else CYBER["line"], width=2)

    def _portal(self, x: int, y: int, color: str) -> None:
        c = self.canvas
        for r, width in [(36, 2), (25, 2), (14, 1)]:
            c.create_oval(x - r, y - r, x + r, y + r, outline=color, width=width)
        c.create_line(x - 44, y, x + 44, y, fill=color, width=1)
        c.create_line(x, y - 44, x, y + 44, fill=color, width=1)

    def _scanlines(self, w: int, h: int) -> None:
        c = self.canvas
        for y in range(0, h, 12):
            c.create_line(0, y, w, y, fill="#050812")
        pulse = int(time.time() * 40) % max(1, h)
        c.create_line(0, pulse, w, pulse, fill=CYBER["pink_dim"], width=2)

    def _connect(self) -> None:
        self.client_badge.configure(text=f"RIGHT NODE // {self._client_host()}")
        self.link.connect(self._client_host(), self._client_port(), self._token(), self._identity())

    def _auto_connect(self) -> None:
        self.root.after(600, self._connect)
        self.root.after(5000, self._auto_retry)

    def _auto_retry(self) -> None:
        if not self.link.connected and not self.link.connecting:
            self._connect()
        self.root.after(5000, self._auto_retry)

    def _change_lang(self, _event=None) -> None:
        self.lang = self.lang_box.get()
        self.config["language"] = self.lang
        (app_dir() / "config.json").write_text(json.dumps(self.config, indent=2), encoding="utf-8")
        self._log(f"Lingua impostata: {self.lang}. Riavvia la UI per aggiornare tutte le etichette.")

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
            elif kind == "disconnected":
                self.status.configure(text=self.text["status_disconnected"], fg="#ff5c7a")
                self._draw_layout()
        self.root.after(80, self._tick)

    def _handle_frame(self, message: dict) -> None:
        kind = message.get("type")
        payload = message.get("payload", {})
        if kind == "hello":
            self.status.configure(text=self.text["status_connected"], fg="#39e58c")
            self._log(f"Client: {payload.get('name')} {payload.get('width')}x{payload.get('height')}")
            self._draw_layout()
        elif kind == "edge" and payload.get("edge") == "left":
            self._log("Il client ha raggiunto il bordo sinistro: ritorno a Windows.")
            self.engine.edge_left()
        elif kind == "pulse_ack":
            self._log("Pulse OK dal client.")
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
        self.engine.running = False
        if self.discovery_beacon:
            self.discovery_beacon.close()
        if self.discovery_listener:
            self.discovery_listener.close()
        self.link.disconnect()


if __name__ == "__main__":
    KyMoRemApp().run()
