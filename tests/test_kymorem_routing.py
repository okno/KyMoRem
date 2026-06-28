from __future__ import annotations

import json
import sys
import queue
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
PY_RUNTIME = ROOT / "runtime" / "python"
sys.path.insert(0, str(PY_RUNTIME))


class RoutingLayoutTests(unittest.TestCase):
    def test_diagonal_positions_keep_both_active_edges(self) -> None:
        import kymorem_server as server

        self.assertEqual(server.position_from_grid(-1, 1), "left/down")
        self.assertEqual(server.position_label_from_grid(-3, 2), "Left + Down")
        self.assertEqual(server.grid_from_position("Left + Down"), (-1, 1))
        self.assertEqual(server.client_edges_from_grid(-2, 4), ["left", "down"])

    def test_cardinal_positions_stay_cardinal(self) -> None:
        import kymorem_server as server

        self.assertEqual(server.position_from_grid(1, 0), "right")
        self.assertEqual(server.position_from_grid(0, -1), "up")
        self.assertEqual(server.client_edges_from_grid(0, -2), ["up"])

    def test_edge_detection_uses_inset_and_ignores_hot_corners(self) -> None:
        import kymorem_server as server

        engine = server.ControlEngine.__new__(server.ControlEngine)
        engine.left = 0
        engine.top = 0
        engine.w = 100
        engine.h = 80

        self.assertEqual(engine._host_edge(97, 40), "right")
        self.assertEqual(engine._host_edge(50, 2), "up")
        self.assertEqual(engine._host_edge(50, 77), "down")
        self.assertIsNone(engine._host_edge(99, 0))
        self.assertIsNone(engine._host_edge(0, 79))

    def test_edge_detection_uses_virtual_screen_coordinates(self) -> None:
        import kymorem_server as server

        engine = server.ControlEngine.__new__(server.ControlEngine)
        engine.left = -1920
        engine.top = -200
        engine.w = 3840
        engine.h = 1280

        self.assertIsNone(engine._host_edge(0, 400))
        self.assertEqual(engine._host_edge(1918, 400), "right")
        self.assertEqual(engine._host_edge(-1920, 400), "left")
        self.assertEqual(engine._host_edge(0, -200), "up")
        self.assertEqual(engine._host_edge(0, 1078), "down")
        self.assertIsNone(engine._host_edge(1918, -200))

    def test_wheel_burst_is_coalesced_and_capped(self) -> None:
        import kymorem_server as server

        engine = server.ControlEngine.__new__(server.ControlEngine)
        engine.events = queue.Queue()
        engine.input_queue = queue.Queue(maxsize=1024)
        engine.coalesce_lock = threading.Lock()
        engine.pending_move_dx = 0
        engine.pending_move_dy = 0
        engine.pending_wheel_dx = 0
        engine.pending_wheel_dy = 0
        engine.last_input_drop_log = 0.0

        for _ in range(1000):
            engine._queue_remote("wheel", dy=server.WHEEL_DELTA_UNIT)

        self.assertTrue(engine.input_queue.empty())
        self.assertEqual(engine.pending_wheel_dy, server.MAX_PENDING_WHEEL_STEPS * server.WHEEL_DELTA_UNIT)
        dx, dy, wheel_dx, wheel_dy = engine._take_coalesced_inputs()
        self.assertEqual((dx, dy), (0, 0))
        self.assertEqual(wheel_dx, 0)
        self.assertEqual(wheel_dy, server.MAX_WHEEL_STEPS_PER_FLUSH * server.WHEEL_DELTA_UNIT)
        self.assertEqual(
            engine.pending_wheel_dy,
            (server.MAX_PENDING_WHEEL_STEPS - server.MAX_WHEEL_STEPS_PER_FLUSH) * server.WHEEL_DELTA_UNIT,
        )

        _dx, _dy, _wheel_dx, wheel_dy = engine._take_coalesced_inputs()
        self.assertEqual(wheel_dy, server.MAX_WHEEL_STEPS_PER_FLUSH * server.WHEEL_DELTA_UNIT)
        self.assertEqual(engine.pending_wheel_dy, 0)

    def test_wheel_remainders_and_horizontal_axis_are_preserved(self) -> None:
        import kymorem_server as server

        engine = server.ControlEngine.__new__(server.ControlEngine)
        engine.events = queue.Queue()
        engine.input_queue = queue.Queue(maxsize=1024)
        engine.coalesce_lock = threading.Lock()
        engine.pending_move_dx = 0
        engine.pending_move_dy = 0
        engine.pending_wheel_dx = 0
        engine.pending_wheel_dy = 0
        engine.last_input_drop_log = 0.0

        engine._queue_remote("wheel", dy=60)
        self.assertEqual(engine._take_coalesced_inputs(), (0, 0, 0, 0))
        self.assertEqual(engine.pending_wheel_dy, 60)
        engine._queue_remote("wheel", dx=server.WHEEL_DELTA_UNIT * 100, dy=60)
        self.assertEqual(
            engine._take_coalesced_inputs(),
            (0, 0, server.MAX_WHEEL_STEPS_PER_FLUSH * server.WHEEL_DELTA_UNIT, server.WHEEL_DELTA_UNIT),
        )

    def test_pending_edge_take_is_cancelled_when_pointer_leaves_edge(self) -> None:
        import kymorem_server as server

        logs: list[str] = []

        class Engine:
            def _host_edge(self, _x: int, _y: int) -> str | None:
                return "left"

        app = server.KyMoRemApp.__new__(server.KyMoRemApp)
        app.server_active = True
        app.selected_client = "linux-iMac:54865"
        app.engine = Engine()
        app.link = type("Link", (), {"endpoint": ("linux-iMac", 54865)})()
        app._log = logs.append
        app._pointer_inside_ui = lambda _x, _y: False
        app._clear_pending_take = server.KyMoRemApp._clear_pending_take.__get__(app, server.KyMoRemApp)
        app._set_pending_take = server.KyMoRemApp._set_pending_take.__get__(app, server.KyMoRemApp)
        app._consume_pending_take = server.KyMoRemApp._consume_pending_take.__get__(app, server.KyMoRemApp)
        app._set_pending_take(
            {"name": "linux-iMac", "host": "linux-iMac", "port": 54865},
            "right",
            {"direction": "right", "ts": time.monotonic()},
            requires_edge=True,
        )

        with mock.patch.object(server, "get_cursor", return_value=(100, 100)):
            self.assertIsNone(app._consume_pending_take())

        self.assertIn("bordo", logs[-1])

    def test_pending_take_rejects_unexpected_connected_endpoint(self) -> None:
        import kymorem_server as server

        logs: list[str] = []

        class Engine:
            def _host_edge(self, _x: int, _y: int) -> str | None:
                return "right"

        app = server.KyMoRemApp.__new__(server.KyMoRemApp)
        app.server_active = True
        app.selected_client = "client-b:54865"
        app.engine = Engine()
        app.link = type("Link", (), {"endpoint": ("client-a", 54865)})()
        app._log = logs.append
        app._pointer_inside_ui = lambda _x, _y: False
        app._clear_pending_take = server.KyMoRemApp._clear_pending_take.__get__(app, server.KyMoRemApp)
        app._set_pending_take = server.KyMoRemApp._set_pending_take.__get__(app, server.KyMoRemApp)
        app._consume_pending_take = server.KyMoRemApp._consume_pending_take.__get__(app, server.KyMoRemApp)
        app._set_pending_take(
            {"name": "client-b", "host": "client-b", "port": 54865},
            "right",
            {"direction": "right", "ts": time.monotonic()},
            requires_edge=True,
        )

        with mock.patch.object(server, "get_cursor", return_value=(100, 100)):
            self.assertIsNone(app._consume_pending_take())

        self.assertIn("endpoint", logs[-1])

    def test_edge_route_falls_back_to_only_enabled_client(self) -> None:
        import kymorem_server as server

        app = server.KyMoRemApp.__new__(server.KyMoRemApp)
        app.server_active = True
        app.selected_client = ""
        app.events = queue.Queue()
        app.config = {
            "clients": [
                {"name": "linux-iMac", "host": "10.0.0.80", "port": 54865, "x": 1, "y": 0, "enabled": True}
            ]
        }
        app.link = type("Link", (), {"connected": True, "endpoint": ("10.0.0.80", 54865)})()
        app._client_edges = server.KyMoRemApp._client_edges.__get__(app, server.KyMoRemApp)
        app._fallback_route_client = server.KyMoRemApp._fallback_route_client.__get__(app, server.KyMoRemApp)
        app._route_from_edge = server.KyMoRemApp._route_from_edge.__get__(app, server.KyMoRemApp)

        self.assertTrue(app._route_from_edge("down", {"direction": "down"}))
        self.assertEqual(app.selected_client, "10.0.0.80:54865")

        events = []
        while not app.events.empty():
            events.append(app.events.get_nowait())

        self.assertIn(("select", "10.0.0.80:54865"), events)
        self.assertTrue(any(kind == "log" and "fallback" in payload for kind, payload in events))

    def test_startup_prunes_smoke_and_stale_discovery_clients(self) -> None:
        import kymorem_server as server

        app = server.KyMoRemApp.__new__(server.KyMoRemApp)
        app.discovered_clients = {}
        app.selected_client = ""
        app.config = {
            "clients": [
                {"name": "linux-iMac", "host": "10.0.0.80", "port": 54865, "x": -1, "y": 1, "source": "manual"},
                {"name": "win7-x64-smoke", "host": "192.168.43.246", "port": 54965, "x": 0, "y": 1, "source": "discovery"},
                {"name": "old-discovery", "host": "10.0.0.99", "port": 54865, "x": 1, "y": 0, "source": "discovery"},
            ]
        }

        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch.object(server, "app_dir", return_value=Path(tmp)):
                self.assertTrue(app._prune_transient_clients(startup=True))

        self.assertEqual(len(app.config["clients"]), 1)
        self.assertEqual(app.config["clients"][0]["name"], "linux-iMac")

    def test_layout_metrics_keep_server_centered_for_asymmetric_clients(self) -> None:
        import kymorem_server as server

        app = server.KyMoRemApp.__new__(server.KyMoRemApp)
        app.config = {
            "clients": [
                {"name": "right", "host": "10.0.0.2", "port": 54865, "x": 1, "y": 0},
                {"name": "far-right", "host": "10.0.0.3", "port": 54865, "x": 4, "y": 0},
            ]
        }
        center_x, center_y, cell_w, cell_h, _node_w, _node_h = app._layout_metrics(1280, 720)
        self.assertEqual((center_x, center_y), (640, 360))
        self.assertGreater(cell_w, 0)
        self.assertGreater(cell_h, 0)

        app.config = {
            "clients": [
                {"name": "left", "host": "10.0.0.4", "port": 54865, "x": -3, "y": 0},
                {"name": "down", "host": "10.0.0.5", "port": 54865, "x": 0, "y": 2},
            ]
        }
        center_x, center_y, _cell_w, _cell_h, _node_w, _node_h = app._layout_metrics(1024, 576)
        self.assertEqual((center_x, center_y), (512, 288))


class LinuxClientPointerTests(unittest.TestCase):
    def test_linux_wheel_steps_are_capped(self) -> None:
        import kymorem_client as client

        self.assertEqual(client.wheel_steps(0), 0)
        self.assertEqual(client.wheel_steps(1), 0)
        self.assertEqual(client.wheel_steps(119), 0)
        self.assertEqual(client.wheel_steps(120), 1)
        self.assertEqual(client.wheel_steps(120 * 1000), client.MAX_WHEEL_STEPS_PER_FRAME)

    def test_linux_client_absolute_pointer_clamps_to_screen(self) -> None:
        import kymorem_client as client

        calls: list[tuple[str, ...]] = []

        class Result:
            returncode = 0
            stderr = ""
            stdout = ""

        def fake_xdotool(*args: str) -> Result:
            calls.append(args)
            return Result()

        original = client.run_xdotool
        try:
            client.run_xdotool = fake_xdotool
            agent = client.ClientAgent.__new__(client.ClientAgent)
            agent.width = 100
            agent.height = 60
            agent.pointer_x = 8
            agent.pointer_y = 30

            agent.move_pointer(-50, 80)

            self.assertEqual(agent.pointer_x, 0)
            self.assertEqual(agent.pointer_y, 59)
            self.assertIn(("mousemove", "0", "59"), calls)
        finally:
            client.run_xdotool = original

    def test_linux_client_reports_all_corner_edges(self) -> None:
        import kymorem_client as client

        self.assertEqual(client.edge_names_from_pointer(0, 59, 100, 60), ["left", "down"])
        self.assertEqual(client.edge_names_from_pointer(99, 0, 100, 60), ["right", "up"])


class TokenResolutionTests(unittest.TestCase):
    def test_runtime_token_prefers_sidecar_token_file(self) -> None:
        import kymorem_common as common

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            exe = root / "KyMoRemClient-Win7-x64.exe"
            exe.write_text("", encoding="utf-8")
            sidecar = root / "kymorem-token.txt"
            sidecar.write_text("shared-secret\n", encoding="utf-8")
            (root / "kymorem-config.json").write_text(json.dumps({"token": "config-secret"}), encoding="utf-8")

            resolved = common.discover_runtime_token(argv0=str(exe), cwd=root, env={}, home=root / "home")

        self.assertIsNotNone(resolved)
        self.assertEqual(resolved.value, "shared-secret")
        self.assertEqual(resolved.source, "sidecar_token")
        self.assertTrue(resolved.path.endswith("kymorem-token.txt"))

    def test_runtime_token_reads_sidecar_config_json(self) -> None:
        import kymorem_common as common

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            exe = root / "KyMoRemClient-Win7-x86.exe"
            exe.write_text("", encoding="utf-8")
            config = root / "kymorem-config.json"
            config.write_text(json.dumps({"token": "config-secret"}), encoding="utf-8")

            resolved = common.discover_runtime_token(argv0=str(exe), cwd=root, env={}, home=root / "home")

        self.assertIsNotNone(resolved)
        self.assertEqual(resolved.value, "config-secret")
        self.assertEqual(resolved.source, "sidecar_config")
        self.assertTrue(resolved.path.endswith("kymorem-config.json"))

    def test_runtime_token_reads_app_config_when_sidecars_are_missing(self) -> None:
        import kymorem_common as common

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            exe = root / "KyMoRemClient-Win7-x86.exe"
            exe.write_text("", encoding="utf-8")
            appdata = root / "AppData" / "Roaming"
            config_dir = appdata / "KyMoRem"
            config_dir.mkdir(parents=True)
            (config_dir / "config.json").write_text(json.dumps({"token": "saved-secret"}), encoding="utf-8")

            resolved = common.discover_runtime_token(
                argv0=str(exe),
                cwd=root,
                env={"APPDATA": str(appdata)},
                home=root / "home",
            )

        self.assertIsNotNone(resolved)
        self.assertEqual(resolved.value, "saved-secret")
        self.assertEqual(resolved.source, "app_config")
        self.assertTrue(resolved.path.endswith("config.json"))


class WindowsClientPointerTests(unittest.TestCase):
    def test_windows_firewall_commands_stay_private_lan_scoped(self) -> None:
        import kymorem_windows_client as client

        commands = client.firewall_rule_commands(54865, "add")

        self.assertEqual(len(commands), 2)
        self.assertTrue(any("protocol=TCP" in part for part in commands[0]))
        self.assertTrue(any("profile=private" in part for part in commands[0]))
        self.assertTrue(any("remoteip=LocalSubnet" in part for part in commands[0]))
        self.assertTrue(any("protocol=UDP" in part for part in commands[1]))
        self.assertTrue(any(f"localport={client.DISCOVERY_PORT}" in part for part in commands[1]))

    def test_windows_firewall_install_ignores_loopback_bind(self) -> None:
        import kymorem_windows_client as client

        logs: list[str] = []
        with mock.patch.object(sys, "argv", ["kymorem_windows_client.py", "--bind", "127.0.0.1", "--install-firewall-rules"]):
            with mock.patch.object(client, "log", side_effect=logs.append):
                with mock.patch.object(client, "configure_firewall_rules") as configure:
                    self.assertEqual(client.main(), 0)

        configure.assert_not_called()
        self.assertTrue(any("loopback bind" in message for message in logs))

    def test_windows_firewall_auto_setup_requests_elevation_when_rules_are_missing(self) -> None:
        import kymorem_windows_client as client

        logs: list[str] = []
        with mock.patch.object(client, "log", side_effect=logs.append):
            with mock.patch.object(client, "firewall_rules_present", side_effect=[False, True]) as present:
                with mock.patch.object(client, "is_elevated", return_value=False):
                    with mock.patch.object(client, "request_elevated_firewall_install", return_value=True) as elevate:
                        with mock.patch.object(client, "configure_firewall_rules") as configure:
                            client.ensure_firewall_rules("0.0.0.0", 54865)

        self.assertEqual(present.call_count, 2)
        elevate.assert_called_once_with("0.0.0.0", 54865)
        configure.assert_not_called()
        self.assertTrue(any("requesting one-time private LAN access setup" in message for message in logs))
        self.assertTrue(any("Windows Firewall ready" in message for message in logs))

    def test_windows_firewall_auto_setup_skips_when_rules_exist(self) -> None:
        import kymorem_windows_client as client

        with mock.patch.object(client, "firewall_rules_present", return_value=True) as present:
            with mock.patch.object(client, "request_elevated_firewall_install") as elevate:
                with mock.patch.object(client, "configure_firewall_rules") as configure:
                    client.ensure_firewall_rules("0.0.0.0", 54865)

        present.assert_called_once_with(54865)
        elevate.assert_not_called()
        configure.assert_not_called()

    def test_windows_client_virtual_edges_use_left_top_offsets(self) -> None:
        import kymorem_windows_client as client

        self.assertEqual(
            client.edge_names_from_pointer(-1920, 1079, -1920, -200, 3840, 1280),
            ["left", "down"],
        )
        self.assertEqual(
            client.edge_names_from_pointer(1919, -200, -1920, -200, 3840, 1280),
            ["right", "up"],
        )
        self.assertEqual(client.edge_names_from_pointer(0, 400, -1920, -200, 3840, 1280), [])

    def test_windows_wheel_delta_uses_whole_steps(self) -> None:
        import kymorem_windows_client as client

        self.assertEqual(client.clamp_wheel_delta(119), 0)
        self.assertEqual(client.clamp_wheel_delta(120), 120)
        self.assertEqual(
            client.clamp_wheel_delta(120 * 1000),
            client.MAX_WHEEL_STEPS_PER_FRAME * client.WHEEL_DELTA_UNIT,
        )

    def test_windows_client_keepalive_is_acknowledged(self) -> None:
        import kymorem_windows_client as client

        sent: list[dict] = []

        class Link:
            def send(self, message: dict) -> None:
                sent.append(message)

        agent = client.WindowsClientAgent.__new__(client.WindowsClientAgent)
        agent.name = "win7-client"
        agent.width = 1920
        agent.height = 1080

        agent.dispatch(Link(), "keepalive", {})

        self.assertEqual(len(sent), 1)
        self.assertEqual(sent[0]["type"], "keepalive_ack")
        self.assertEqual(sent[0]["payload"]["name"], "win7-client")
        self.assertEqual(sent[0]["payload"]["screen"], "1920x1080")


if __name__ == "__main__":
    unittest.main()
