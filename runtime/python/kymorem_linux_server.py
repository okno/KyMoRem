from __future__ import annotations

import argparse
import json
import queue
import socket
import subprocess
import threading
import time
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, ttk

from kymorem_common import DEFAULT_CONFIG, PORT, VERSION, frame, runtime_config_dir
from kymorem_crypto import CryptoError, secure_connect, validate_token


GRID_SCALE = 180
EDGE_MARGIN = 2
EDGE_POLL_INTERVAL = 0.02
EDGE_TAKE_COOLDOWN = 0.55
REMOTE_POLL_INTERVAL = 0.016
RELEASE_EDGE_MARGIN = 2
POSITION_TO_GRID = {"right": (1, 0), "left": (-1, 0), "up": (0, -1), "down": (0, 1)}
RETURN_EDGE = {"right": "left", "left": "right", "up": "down", "down": "up"}


def app_dir() -> Path:
    path = runtime_config_dir()
    path.mkdir(parents=True, exist_ok=True)
    return path


def load_config() -> dict:
    path = app_dir() / "config.json"
    if not path.exists():
        config = dict(DEFAULT_CONFIG)
        config["mode"] = "server"
        config["server_on"] = True
        path.write_text(json.dumps(config, indent=2), encoding="utf-8")
    with path.open("r", encoding="utf-8-sig") as handle:
        return json.load(handle)


def save_config(config: dict) -> None:
    (app_dir() / "config.json").write_text(json.dumps(config, indent=2), encoding="utf-8")


def normalize_client(client: dict, index: int = 0) -> dict:
    item = dict(client)
    item.setdefault("name", f"client-{index + 1}")
    item.setdefault("host", "127.0.0.1")
    item.setdefault("port", PORT)
    if "x" not in item or "y" not in item:
        x, y = POSITION_TO_GRID.get(str(item.get("position", "right")), (index + 1, 0))
        item["x"] = x
        item["y"] = y
    item.setdefault("enabled", True)
    item.setdefault("approved", True)
    return item


def client_key(client: dict) -> str:
    return f"{client.get('host', '')}:{int(client.get('port', PORT))}"


def screen_size() -> tuple[int, int]:
    try:
        output = subprocess.check_output(["xdotool", "getdisplaygeometry"], text=True, timeout=0.5)
        w, h = output.split()[:2]
        return int(w), int(h)
    except Exception:
        return 1920, 1080


def pointer_location() -> tuple[int, int]:
    output = subprocess.check_output(["xdotool", "getmouselocation", "--shell"], text=True, timeout=0.5)
    values: dict[str, int] = {}
    for line in output.splitlines():
        if "=" in line:
            key, value = line.split("=", 1)
            if key in {"X", "Y"}:
                values[key] = int(value)
    return values.get("X", 0), values.get("Y", 0)


def move_pointer(x: int, y: int) -> None:
    subprocess.run(["xdotool", "mousemove", str(int(x)), str(int(y))], check=False)


class RemoteLink:
    def __init__(self, events: queue.Queue):
        self.events = events
        self.lock = threading.Lock()
        self.sock: socket.socket | None = None
        self.secure = None
        self.connected = False
        self.endpoint: tuple[str, int] | None = None
        self.generation = 0

    def connect(self, host: str, port: int, token: str, identity: dict) -> None:
        self.disconnect()
        with self.lock:
            self.generation += 1
            generation = self.generation
        threading.Thread(target=self._connect_thread, args=(generation, host, int(port), token, identity), daemon=True).start()

    def _connect_thread(self, generation: int, host: str, port: int, token: str, identity: dict) -> None:
        sock = None
        try:
            self.events.put(("log", f"Connessione Linux server a {host}:{port}..."))
            sock = socket.create_connection((host, port), timeout=5)
            sock.settimeout(None)
            secure = secure_connect(sock, token, identity)
            with self.lock:
                if generation != self.generation:
                    sock.close()
                    return
                self.sock = sock
                self.secure = secure
                self.connected = True
                self.endpoint = (host, port)
            secure.send(frame("hello", role="server", name=identity.get("name", "Linux Server"), version=VERSION))
            self.events.put(("log", f"Connesso a {host}:{port} // {secure.suite}"))
            for message in secure.read_frames():
                self.events.put(("frame", message))
        except Exception as exc:
            self.events.put(("log", f"Connessione fallita: {exc}"))
        finally:
            with self.lock:
                if generation == self.generation:
                    self.connected = False
                    self.sock = None
                    self.secure = None
                    self.endpoint = None
            if sock:
                try:
                    sock.close()
                except OSError:
                    pass

    def disconnect(self) -> None:
        with self.lock:
            sock = self.sock
            secure = self.secure
            self.sock = None
            self.secure = None
            self.connected = False
            self.endpoint = None
            self.generation += 1
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
            sock = self.sock
        if not secure:
            return
        try:
            old_timeout = sock.gettimeout() if sock else None
            if sock:
                sock.settimeout(0.75)
            secure.send(frame(kind, **payload))
            if sock:
                sock.settimeout(old_timeout)
        except Exception as exc:
            self.events.put(("log", f"Invio fallito: {exc}"))
            self.disconnect()


class LinuxControlEngine:
    def __init__(self, link: RemoteLink, route_callback, log_callback):
        self.link = link
        self.route_callback = route_callback
        self.log = log_callback
        self.enabled = False
        self.remote = False
        self.active_direction = "right"
        self.last_edge_ts = 0.0
        self.last_point = (0, 0)
        self.running = True
        threading.Thread(target=self._loop, daemon=True).start()

    def _loop(self) -> None:
        while self.running:
            try:
                if self.enabled:
                    self._tick()
            except Exception:
                pass
            time.sleep(EDGE_POLL_INTERVAL if not self.remote else REMOTE_POLL_INTERVAL)

    def _tick(self) -> None:
        width, height = screen_size()
        x, y = pointer_location()
        if self.remote:
            lx, ly = self.last_point
            dx, dy = x - lx, y - ly
            if dx or dy:
                self.link.send("move", dx=dx, dy=dy)
                self.last_point = (x, y)
            return
        edge = self._edge(x, y, width, height)
        now = time.monotonic()
        if edge and now - self.last_edge_ts > EDGE_TAKE_COOLDOWN:
            self.last_edge_ts = now
            self.route_callback(edge, x, y, width, height)

    def _edge(self, x: int, y: int, width: int, height: int) -> str:
        if x <= EDGE_MARGIN:
            return "left"
        if x >= width - EDGE_MARGIN - 1:
            return "right"
        if y <= EDGE_MARGIN:
            return "up"
        if y >= height - EDGE_MARGIN - 1:
            return "down"
        return ""

    def enter_remote(self, direction: str, x: int, y: int, width: int, height: int) -> None:
        self.remote = True
        self.active_direction = direction
        self.last_point = (x, y)
        if direction == "right":
            move_pointer(width - RELEASE_EDGE_MARGIN - 2, y)
        elif direction == "left":
            move_pointer(RELEASE_EDGE_MARGIN + 2, y)
        elif direction == "up":
            move_pointer(x, RELEASE_EDGE_MARGIN + 2)
        elif direction == "down":
            move_pointer(x, height - RELEASE_EDGE_MARGIN - 2)

    def release(self) -> None:
        self.remote = False
        self.link.send("release")


class KyMoRemLinuxServer:
    def __init__(self) -> None:
        self.config = load_config()
        self.events: queue.Queue = queue.Queue()
        self.link = RemoteLink(self.events)
        self.engine = LinuxControlEngine(self.link, self._route_from_edge, lambda m: self.events.put(("log", m)))
        self.engine.enabled = bool(self.config.get("server_on", True))
        self.clients = [normalize_client(item, idx) for idx, item in enumerate(self.config.get("clients", []))]
        self.selected = client_key(self.clients[0]) if self.clients else ""
        self.root = tk.Tk()
        self.root.title(f"KyMoRem Linux Server {VERSION} // KMR Neon Route Console")
        self.root.configure(bg="#090d12")
        self.root.geometry("1280x760")
        self._build_ui()
        self._refresh_clients()
        self._pump_events()

    def _build_ui(self) -> None:
        style = ttk.Style()
        style.theme_use("clam")
        style.configure("KMR.TButton", background="#202733", foreground="#5be7ff", borderwidth=0, padding=8)
        style.configure("KMR.TCombobox", fieldbackground="#1b222c", background="#1b222c", foreground="#ffffff")
        header = tk.Frame(self.root, bg="#090d12")
        header.pack(fill="x", padx=18, pady=(18, 8))
        tk.Label(header, text="KyMoRem", fg="#5be7ff", bg="#090d12", font=("Consolas", 36, "bold")).pack(side="left")
        tk.Label(header, text="Linux Server // KMR", fg="#b7c6ff", bg="#090d12", font=("Consolas", 12, "bold")).pack(side="left", padx=20)
        self.client_var = tk.StringVar()
        self.client_select = ttk.Combobox(header, textvariable=self.client_var, state="readonly", style="KMR.TCombobox", width=38)
        self.client_select.pack(side="right", padx=8)
        self.client_select.bind("<<ComboboxSelected>>", lambda _event: self._select_client())

        body = tk.Frame(self.root, bg="#111720", highlightbackground="#354052", highlightthickness=1)
        body.pack(fill="both", expand=True, padx=18, pady=8)
        self.canvas = tk.Canvas(body, bg="#121820", highlightthickness=0)
        self.canvas.pack(fill="both", expand=True, padx=18, pady=18)

        footer = tk.Frame(self.root, bg="#090d12")
        footer.pack(fill="x", padx=18, pady=(8, 14))
        for label, command in [
            ("SERVER ON/OFF", self._toggle_server),
            ("CONNETTI CLIENT", self._connect_selected),
            ("PRENDI CONTROLLO", self._take_selected),
            ("RILASCIA", self._release),
            ("AGGIORNA", self._refresh_clients),
            ("CONTROL CENTER", self._control_center),
        ]:
            ttk.Button(footer, text=label, command=command, style="KMR.TButton").pack(side="left", padx=5)
        self.status = tk.Label(self.root, text="", fg="#50ffa5", bg="#090d12", font=("Consolas", 10))
        self.status.pack(fill="x", padx=22, pady=(0, 10))

    def _refresh_clients(self) -> None:
        self.clients = [normalize_client(item, idx) for idx, item in enumerate(self.config.get("clients", []))]
        values = [f"{client.get('name')} // {client_key(client)}" for client in self.clients if client.get("enabled", True)]
        self.client_select.configure(values=values)
        if values and not self.client_var.get():
            self.client_var.set(values[0])
            self.selected = client_key(self.clients[0])
        self._draw_map()

    def _select_client(self) -> None:
        raw = self.client_var.get()
        if "//" in raw:
            self.selected = raw.split("//", 1)[1].strip()
        self._draw_map()

    def _client_by_key(self, key: str) -> dict | None:
        return next((client for client in self.clients if client_key(client) == key), None)

    def _draw_map(self) -> None:
        self.canvas.delete("all")
        w = max(900, self.canvas.winfo_width())
        h = max(500, self.canvas.winfo_height())
        cx, cy = w // 2, h // 2
        self.canvas.create_text(16, 16, text="Mappa routing KMR // Linux", fill="#cfe6ff", anchor="nw", font=("Consolas", 11, "bold"))
        self._draw_node(cx, cy, "SERVER", "linux host", "#5be7ff", True)
        for client in self.clients:
            x = cx + int(client.get("x", 1)) * GRID_SCALE
            y = cy + int(client.get("y", 0)) * GRID_SCALE
            selected = client_key(client) == self.selected
            color = "#50ffa5" if selected else "#5be7ff"
            self.canvas.create_line(cx, cy, x, y, fill=color, width=2)
            self._draw_node(x, y, str(client.get("name")), f"{client_key(client)}", color, selected)
        self.status.configure(text=f"SERVER {'ON' if self.engine.enabled else 'OFF'} // selected {self.selected or 'none'}")

    def _draw_node(self, x: int, y: int, title: str, detail: str, color: str, selected: bool) -> None:
        self.canvas.create_rectangle(x - 95, y - 48, x + 95, y + 48, outline=color, width=2, fill="#1b222c")
        self.canvas.create_text(x - 78, y - 18, text=title.upper(), fill=color, anchor="w", font=("Consolas", 13, "bold"))
        self.canvas.create_text(x - 78, y + 10, text=detail, fill="#ffffff", anchor="w", font=("Consolas", 9, "bold"))
        self.canvas.create_text(x + 66, y + 26, text="ONLINE" if selected else "STANDBY", fill="#50ffa5" if selected else "#cfe6ff", anchor="e", font=("Consolas", 9, "bold"))

    def _toggle_server(self) -> None:
        self.engine.enabled = not self.engine.enabled
        self.config["mode"] = "server"
        self.config["server_on"] = self.engine.enabled
        save_config(self.config)
        self._draw_map()

    def _connect_selected(self) -> None:
        client = self._client_by_key(self.selected)
        if not client:
            return
        token = str(self.config.get("token", ""))
        try:
            validate_token(token)
        except CryptoError as exc:
            messagebox.showerror("KyMoRem token", str(exc))
            return
        self.link.connect(str(client.get("host")), int(client.get("port", PORT)), token, {"role": "server", "name": "KyMoRem Linux", "platform": "linux", "version": VERSION})

    def _take_selected(self) -> None:
        client = self._client_by_key(self.selected)
        if not client:
            return
        self._connect_selected()
        direction = str(client.get("position") or "right").split("/")[0]
        width, height = screen_size()
        self._enter_when_connected(direction, width // 2, height // 2, width, height, 0.5, 0.5)

    def _route_from_edge(self, edge: str, x: int, y: int, width: int, height: int) -> None:
        client = next((item for item in self.clients if (int(item.get("x", 0)), int(item.get("y", 0))) == POSITION_TO_GRID.get(edge)), None)
        if not client:
            return
        self.selected = client_key(client)
        self.client_var.set(f"{client.get('name')} // {self.selected}")
        self._connect_selected()
        self._enter_when_connected(edge, x, y, width, height, x / max(1, width - 1), y / max(1, height - 1))

    def _enter_when_connected(self, direction: str, x: int, y: int, width: int, height: int, x_ratio: float, y_ratio: float, attempts: int = 0) -> None:
        if self.link.connected:
            self.link.send("enter", edge=RETURN_EDGE.get(direction, "left"), x_ratio=x_ratio, y_ratio=y_ratio)
            self.engine.enter_remote(direction, x, y, width, height)
            return
        if attempts >= 30:
            self.status.configure(text="Client non connesso: enter annullato.")
            return
        self.root.after(100, lambda: self._enter_when_connected(direction, x, y, width, height, x_ratio, y_ratio, attempts + 1))

    def _release(self) -> None:
        self.engine.release()
        self._draw_map()

    def _control_center(self) -> None:
        top = tk.Toplevel(self.root)
        top.title("KyMoRem Control Center")
        top.configure(bg="#111720")
        top.geometry("460x360+%d+%d" % (self.root.winfo_x() + 120, self.root.winfo_y() + 120))
        tk.Label(top, text="KyMoRem Linux Control Center", fg="#5be7ff", bg="#111720", font=("Consolas", 16, "bold")).pack(anchor="w", padx=16, pady=16)
        tk.Label(top, text="X11 server mode uses xdotool pointer polling.\nKeyboard global capture requires an evdev/uinput backend.", fg="#cfe6ff", bg="#111720", justify="left", font=("Consolas", 10)).pack(anchor="w", padx=16)

    def _pump_events(self) -> None:
        try:
            while True:
                kind, payload = self.events.get_nowait()
                if kind == "log":
                    self.status.configure(text=str(payload))
                elif kind == "frame" and payload.get("type") == "edge":
                    self._release()
        except queue.Empty:
            pass
        self.root.after(80, self._pump_events)

    def run(self) -> None:
        self.root.mainloop()


def main() -> int:
    parser = argparse.ArgumentParser(description="KyMoRem Linux server UI")
    parser.add_argument("--no-discovery", action="store_true")
    _args = parser.parse_args()
    app = KyMoRemLinuxServer()
    app.run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
