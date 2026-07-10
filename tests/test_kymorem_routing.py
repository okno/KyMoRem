from __future__ import annotations

import json
import sys
import queue
import tempfile
import threading
import time
import unittest
import ctypes
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

    def test_control_center_geometry_is_centered_on_parent(self) -> None:
        import kymorem_server as server

        self.assertEqual(
            server.centered_child_geometry(100, 80, 900, 700, 430, 520, 0, 0, 1920, 1080),
            "430x520+335+170",
        )

    def test_control_center_geometry_stays_on_screen(self) -> None:
        import kymorem_server as server

        self.assertEqual(
            server.centered_child_geometry(1700, 900, 400, 300, 430, 520, 0, 0, 1920, 1080),
            "430x520+1490+560",
        )

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

    def test_release_drops_pending_wheel_backlog(self) -> None:
        import kymorem_server as server

        sent: list[tuple[str, dict]] = []
        engine = server.ControlEngine.__new__(server.ControlEngine)
        engine.remote = True
        engine.active_direction = "down"
        engine.left = 0
        engine.top = 0
        engine.w = 100
        engine.h = 80
        engine.events = queue.Queue()
        engine.coalesce_lock = threading.Lock()
        engine.input_queue = queue.Queue(maxsize=1024)
        engine.pending_move_dx = 25
        engine.pending_move_dy = -10
        engine.pending_wheel_dx = server.MAX_PENDING_WHEEL_STEPS * server.WHEEL_DELTA_UNIT
        engine.pending_wheel_dy = server.MAX_PENDING_WHEEL_STEPS * server.WHEEL_DELTA_UNIT
        engine.last_keepalive_ack = 0.0
        engine.last_keepalive_sent = 0.0
        engine.last_edge_ts = 0.0
        engine.button_state = {"left": False}
        engine.key_state = {"VK_A": False}
        engine.cursor_hidden = False
        engine.link = type("Link", (), {"send": lambda _self, kind, **payload: sent.append((kind, payload))})()
        engine.input_queue.put_nowait(("wheel", {"dy": server.WHEEL_DELTA_UNIT}))

        with mock.patch.object(server, "set_cursor"):
            engine.release()

        self.assertEqual(engine.pending_move_dx, 0)
        self.assertEqual(engine.pending_move_dy, 0)
        self.assertEqual(engine.pending_wheel_dx, 0)
        self.assertEqual(engine.pending_wheel_dy, 0)
        self.assertTrue(engine.input_queue.empty())
        self.assertNotIn("wheel", [kind for kind, _payload in sent])
        self.assertEqual(sent[-1][0], "release")

    def test_wheel_flush_is_rate_limited_without_delaying_mouse_move(self) -> None:
        import kymorem_server as server

        sent: list[tuple[str, dict]] = []
        engine = server.ControlEngine.__new__(server.ControlEngine)
        engine.remote = True
        engine.coalesce_lock = threading.Lock()
        engine.input_queue = queue.Queue(maxsize=1024)
        engine.pending_move_dx = 0
        engine.pending_move_dy = 0
        engine.pending_wheel_dx = 0
        engine.pending_wheel_dy = server.WHEEL_DELTA_UNIT
        engine.last_wheel_flush_ts = 10.0
        engine.link = type("Link", (), {"send": lambda _self, kind, **payload: sent.append((kind, payload))})()

        with mock.patch.object(server.time, "monotonic", return_value=10.0 + server.WHEEL_FLUSH_INTERVAL / 2):
            engine._queue_remote("move", dx=7, dy=3)
            engine._flush_coalesced_inputs()

        self.assertEqual(sent, [("move", {"dx": 7, "dy": 3})])
        self.assertEqual(engine.pending_wheel_dy, server.WHEEL_DELTA_UNIT)

        with mock.patch.object(server.time, "monotonic", return_value=10.0 + server.WHEEL_FLUSH_INTERVAL * 2):
            engine._flush_coalesced_inputs()

        self.assertEqual(sent[-1], ("wheel", {"dx": 0, "dy": server.WHEEL_DELTA_UNIT}))

    def test_remote_mode_hides_and_restores_host_cursor(self) -> None:
        import kymorem_server as server

        calls: list[bool] = []

        def fake_show_cursor(show: bool) -> int:
            calls.append(show)
            return 0 if show else -1

        engine = server.ControlEngine.__new__(server.ControlEngine)
        engine.cursor_hidden = False

        with mock.patch.object(server.user32, "ShowCursor", side_effect=fake_show_cursor):
            engine._hide_host_cursor()
            self.assertTrue(engine.cursor_hidden)
            engine._hide_host_cursor()
            engine._show_host_cursor()
            self.assertFalse(engine.cursor_hidden)

        self.assertEqual(calls, [False, True])

    def test_remote_mouse_move_is_consumed_and_sent_as_delta(self) -> None:
        import kymorem_server as server

        moves: list[tuple[str, dict]] = []
        info = server.MSLLHOOKSTRUCT()
        info.pt.x = 520
        info.pt.y = 492
        info.flags = 0
        pointer = ctypes.cast(ctypes.pointer(info), ctypes.c_void_p).value

        engine = server.ControlEngine.__new__(server.ControlEngine)
        engine.remote = True
        engine.anchor = (500, 500)
        engine.last_mouse_point = (500, 500)
        engine.suppress_mouse_move = False
        engine.mouse_hook = None
        engine._queue_remote = lambda kind, **payload: moves.append((kind, payload))

        with mock.patch.object(server, "set_cursor") as set_cursor:
            result = engine._mouse_hook(0, server.WM_MOUSEMOVE, pointer)

        self.assertEqual(result, 1)
        self.assertEqual(moves, [("move", {"dx": 20, "dy": -8})])
        set_cursor.assert_called_once_with(500, 500)

    def test_remote_loop_releases_when_link_is_already_down(self) -> None:
        import kymorem_server as server

        engine = server.ControlEngine.__new__(server.ControlEngine)
        engine.enabled = True
        engine.remote = True
        engine.link = type("Link", (), {"connected": False})()
        engine.events = queue.Queue()
        engine.release = mock.Mock()

        with mock.patch.object(server.time, "sleep"), mock.patch.object(server, "async_down", return_value=False):
            engine._loop_once()

        engine.release.assert_called_once_with(notify_client=False)
        self.assertEqual(engine.events.get_nowait()[0], "log")

    def test_remote_loop_releases_before_disconnect_on_keepalive_timeout(self) -> None:
        import kymorem_server as server

        calls: list[str] = []
        engine = server.ControlEngine.__new__(server.ControlEngine)
        engine.enabled = True
        engine.remote = True
        engine.active_direction = "right"
        engine.last_keepalive_sent = 0.0
        engine.last_keepalive_ack = 0.0
        engine.events = queue.Queue()
        engine.link = type(
            "Link",
            (),
            {
                "connected": True,
                "send": lambda *_args, **_kwargs: calls.append("send"),
                "disconnect": lambda *_args, **_kwargs: calls.append("disconnect"),
            },
        )()
        engine.release = mock.Mock(side_effect=lambda **_kwargs: calls.append("release"))

        with mock.patch.object(server.time, "sleep"), mock.patch.object(server, "async_down", return_value=False):
            engine._loop_once()

        self.assertIn("release", calls)
        self.assertIn("disconnect", calls)
        self.assertLess(calls.index("release"), calls.index("disconnect"))

    def test_screen_edge_routes_even_when_pointer_is_inside_ui_window(self) -> None:
        import kymorem_server as server

        routed: list[tuple[str, dict]] = []
        engine = server.ControlEngine.__new__(server.ControlEngine)
        engine.enabled = True
        engine.remote = False
        engine.left = 0
        engine.top = 0
        engine.w = 100
        engine.h = 80
        engine.anchor = (50, 40)
        engine.last_edge_ts = 0.0
        engine.edge_guard = lambda _x, _y: True
        engine.router = lambda direction, entry: routed.append((direction, entry)) or False
        engine.take = mock.Mock()
        engine._capture_edge_exit = server.ControlEngine._capture_edge_exit.__get__(engine, server.ControlEngine)

        with mock.patch.object(server.time, "sleep"), mock.patch.object(server.time, "monotonic", return_value=10.0), mock.patch.object(server, "get_cursor", return_value=(50, 79)):
            engine._loop_once()

        self.assertEqual(routed[0][0], "down")

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

    def test_unassigned_edge_does_not_fallback_to_only_enabled_client(self) -> None:
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

        self.assertFalse(app._route_from_edge("down", {"direction": "down"}))
        self.assertEqual(app.selected_client, "")

        events = []
        while not app.events.empty():
            events.append(app.events.get_nowait())

        self.assertNotIn(("select", "10.0.0.80:54865"), events)
        self.assertTrue(any(kind == "log" and "Nessun client assegnato al bordo down" in payload for kind, payload in events))

    def test_edge_route_keeps_pending_take_without_requiring_cursor_on_edge(self) -> None:
        import kymorem_server as server

        app = server.KyMoRemApp.__new__(server.KyMoRemApp)
        app.server_active = True
        app.selected_client = ""
        app.events = queue.Queue()
        app.config = {
            "clients": [
                {"name": "windows7", "host": "10.0.0.49", "port": 54865, "x": 0, "y": 1, "enabled": True}
            ]
        }
        app.link = type("Link", (), {"connected": False, "connecting": False, "connect": mock.Mock()})()
        app._fallback_route_client = server.KyMoRemApp._fallback_route_client.__get__(app, server.KyMoRemApp)
        app._set_pending_take = server.KyMoRemApp._set_pending_take.__get__(app, server.KyMoRemApp)
        app._route_from_edge = server.KyMoRemApp._route_from_edge.__get__(app, server.KyMoRemApp)
        app._client_edges = server.KyMoRemApp._client_edges.__get__(app, server.KyMoRemApp)
        app._token = lambda: "token"
        app._identity = lambda: {"name": "server"}

        result = app._route_from_edge("down", {"direction": "down", "ts": time.monotonic()})

        self.assertFalse(result)
        self.assertEqual(app.pending_take_client, "10.0.0.49:54865")
        self.assertFalse(app.pending_take_requires_edge)
        app.link.connect.assert_called_once_with("10.0.0.49", 54865, "token", {"name": "server"})

    def test_edge_route_switches_from_existing_link_to_target_client(self) -> None:
        import kymorem_server as server

        logs: list[str] = []
        app = server.KyMoRemApp.__new__(server.KyMoRemApp)
        app.server_active = True
        app.selected_client = "10.0.0.80:54865"
        app.events = queue.Queue()
        app.config = {
            "clients": [
                {"name": "linux-iMac", "host": "10.0.0.80", "port": 54865, "x": 1, "y": 0, "enabled": True},
                {"name": "windows7", "host": "10.0.0.49", "port": 54865, "x": 0, "y": -1, "enabled": True},
            ]
        }
        app.link = type(
            "Link",
            (),
            {
                "connected": True,
                "connecting": False,
                "endpoint": ("10.0.0.80", 54865),
                "disconnect": mock.Mock(),
                "connect": mock.Mock(),
            },
        )()
        app._log = logs.append
        app._fallback_route_client = server.KyMoRemApp._fallback_route_client.__get__(app, server.KyMoRemApp)
        app._set_pending_take = server.KyMoRemApp._set_pending_take.__get__(app, server.KyMoRemApp)
        app._connect_endpoint = server.KyMoRemApp._connect_endpoint.__get__(app, server.KyMoRemApp)
        app._route_from_edge = server.KyMoRemApp._route_from_edge.__get__(app, server.KyMoRemApp)
        app._client_edges = server.KyMoRemApp._client_edges.__get__(app, server.KyMoRemApp)
        app._token = lambda: "token"
        app._identity = lambda: {"name": "server"}

        result = app._route_from_edge("up", {"direction": "up", "ts": time.monotonic()})

        self.assertFalse(result)
        app.link.disconnect.assert_called_once()
        app.link.connect.assert_called_once_with("10.0.0.49", 54865, "token", {"name": "server"})
        self.assertEqual(app.pending_take_endpoint, ("10.0.0.49", 54865))
        self.assertTrue(any("bordo up -> windows7" in message for message in logs))

    def test_client_edge_routes_to_adjacent_client(self) -> None:
        import kymorem_server as server

        logs: list[str] = []
        app = server.KyMoRemApp.__new__(server.KyMoRemApp)
        app.config = {
            "clients": [
                {"name": "linux-iMac", "host": "10.0.0.80", "port": 54865, "x": 1, "y": 0, "enabled": True},
                {"name": "windows7", "host": "10.0.0.49", "port": 54865, "x": 2, "y": 0, "enabled": True},
            ]
        }
        app.selected_client = "10.0.0.80:54865"
        app.discovered_clients = {}
        app.link = type(
            "Link",
            (),
            {
                "connected": True,
                "connecting": False,
                "endpoint": ("10.0.0.80", 54865),
                "client_info": {"width": 1920, "height": 1080},
                "disconnect": mock.Mock(),
                "connect": mock.Mock(),
            },
        )()
        app.engine = type("Engine", (), {"release": mock.Mock()})()
        app._log = logs.append
        app._refresh_client_list = lambda: None
        app._draw_layout = lambda: None
        app._save_config = lambda: None
        app._token = lambda: "token"
        app._identity = lambda: {"name": "server"}
        app._clear_pending_take = server.KyMoRemApp._clear_pending_take.__get__(app, server.KyMoRemApp)
        app._set_pending_take = server.KyMoRemApp._set_pending_take.__get__(app, server.KyMoRemApp)
        app._connect_endpoint = server.KyMoRemApp._connect_endpoint.__get__(app, server.KyMoRemApp)

        app._handle_client_edge("right", {"edge": "right", "x": 1919, "y": 540, "width": 1920, "height": 1080})

        self.assertEqual(app.selected_client, "10.0.0.49:54865")
        app.engine.release.assert_called_once_with(restore_cursor=False)
        app.link.disconnect.assert_called_once()
        app.link.connect.assert_called_once_with("10.0.0.49", 54865, "token", {"name": "server"})
        self.assertEqual(app.pending_take_direction, "right")
        self.assertAlmostEqual(app.pending_take_entry["y_ratio"], 540 / 1079)
        self.assertTrue(any("linux-iMac bordo right -> windows7" in message for message in logs))

    def test_client_edge_toward_server_releases_when_no_neighbor(self) -> None:
        import kymorem_server as server

        logs: list[str] = []
        app = server.KyMoRemApp.__new__(server.KyMoRemApp)
        app.config = {
            "clients": [
                {"name": "linux-iMac", "host": "10.0.0.80", "port": 54865, "x": 1, "y": 0, "enabled": True}
            ]
        }
        app.selected_client = "10.0.0.80:54865"
        app.link = type("Link", (), {"endpoint": ("10.0.0.80", 54865), "client_info": {}})()
        app.engine = type("Engine", (), {"release": mock.Mock(), "client_edge": mock.Mock()})()
        app._log = logs.append

        app._handle_client_edge("left", {"edge": "left"})

        app.engine.release.assert_called_once_with()
        app.engine.client_edge.assert_not_called()
        self.assertTrue(any("Rientro sul server" in message for message in logs))

    def test_client_edge_routes_after_positions_move_left(self) -> None:
        import kymorem_server as server

        app = server.KyMoRemApp.__new__(server.KyMoRemApp)
        app.config = {
            "clients": [
                {"name": "linux-iMac", "host": "10.0.0.80", "port": 54865, "x": -1, "y": 0, "enabled": True},
                {"name": "windows7", "host": "10.0.0.49", "port": 54865, "x": -2, "y": 0, "enabled": True},
            ]
        }
        app.selected_client = "10.0.0.80:54865"
        app.discovered_clients = {}
        app.link = type(
            "Link",
            (),
            {
                "connected": True,
                "connecting": False,
                "endpoint": ("10.0.0.80", 54865),
                "client_info": {"width": 1920, "height": 1080},
                "disconnect": mock.Mock(),
                "connect": mock.Mock(),
            },
        )()
        app.engine = type("Engine", (), {"release": mock.Mock()})()
        app._log = lambda _message: None
        app._refresh_client_list = lambda: None
        app._draw_layout = lambda: None
        app._save_config = lambda: None
        app._token = lambda: "token"
        app._identity = lambda: {}
        app._clear_pending_take = server.KyMoRemApp._clear_pending_take.__get__(app, server.KyMoRemApp)
        app._set_pending_take = server.KyMoRemApp._set_pending_take.__get__(app, server.KyMoRemApp)
        app._connect_endpoint = server.KyMoRemApp._connect_endpoint.__get__(app, server.KyMoRemApp)

        app._handle_client_edge("left", {"edge": "left", "x": 0, "y": 540, "width": 1920, "height": 1080})

        self.assertEqual(app.selected_client, "10.0.0.49:54865")
        app.link.disconnect.assert_called_once()
        app.link.connect.assert_called_once_with("10.0.0.49", 54865, "token", {})

    def test_client_edge_ignores_pending_clients_after_layout_move(self) -> None:
        import kymorem_server as server

        app = server.KyMoRemApp.__new__(server.KyMoRemApp)
        app.config = {
            "clients": [
                {"name": "linux-iMac", "host": "10.0.0.80", "port": 54865, "x": 1, "y": 0, "enabled": True},
                {
                    "name": "pending-win",
                    "host": "10.0.0.51",
                    "port": 54865,
                    "x": 2,
                    "y": 0,
                    "enabled": True,
                    "source": "discovery_pending",
                },
                {"name": "windows7", "host": "10.0.0.49", "port": 54865, "x": 3, "y": 0, "enabled": True},
            ]
        }
        app.selected_client = "10.0.0.80:54865"
        app.discovered_clients = {}
        app.link = type(
            "Link",
            (),
            {
                "connected": True,
                "connecting": False,
                "endpoint": ("10.0.0.80", 54865),
                "client_info": {"width": 1920, "height": 1080},
                "disconnect": mock.Mock(),
                "connect": mock.Mock(),
            },
        )()
        app.engine = type("Engine", (), {"release": mock.Mock()})()
        app._log = lambda _message: None
        app._refresh_client_list = lambda: None
        app._draw_layout = lambda: None
        app._save_config = lambda: None
        app._token = lambda: "token"
        app._identity = lambda: {}
        app._clear_pending_take = server.KyMoRemApp._clear_pending_take.__get__(app, server.KyMoRemApp)
        app._set_pending_take = server.KyMoRemApp._set_pending_take.__get__(app, server.KyMoRemApp)
        app._connect_endpoint = server.KyMoRemApp._connect_endpoint.__get__(app, server.KyMoRemApp)

        app._handle_client_edge("right", {"edge": "right", "x": 1919, "y": 540, "width": 1920, "height": 1080})

        self.assertEqual(app.selected_client, "10.0.0.49:54865")
        app.link.disconnect.assert_called_once()
        app.link.connect.assert_called_once_with("10.0.0.49", 54865, "token", {})

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

    def test_discovery_claims_preapproved_pending_client_by_name(self) -> None:
        import kymorem_server as server

        logs: list[str] = []
        app = server.KyMoRemApp.__new__(server.KyMoRemApp)
        app.server_active = True
        app.selected_client = ""
        app.discovered_clients = {}
        app.config = {
            "clients": [
                {
                    "name": "windows7",
                    "host": "pending",
                    "port": 54865,
                    "x": 4,
                    "y": 0,
                    "enabled": True,
                    "source": "manual",
                    "approved": True,
                }
            ]
        }
        app.link = type("Link", (), {"connected": False, "connecting": False})()
        app._log = logs.append
        app._update_discovery_badge = lambda: None
        app._save_config = lambda: None
        app._refresh_client_list = lambda: None
        app._draw_layout = lambda: None
        app._discovery_auto_connect = lambda: False

        app._handle_discovery(
            (
                {
                    "type": "discovery_announce",
                    "payload": {
                        "role": "client",
                        "name": "windows7",
                        "host": "10.0.0.90",
                        "port": 54865,
                    },
                },
                ("10.0.0.90", 54866),
            )
        )

        self.assertEqual(len(app.config["clients"]), 1)
        self.assertEqual(app.config["clients"][0]["host"], "10.0.0.90")
        self.assertEqual(app.config["clients"][0]["x"], 4)
        self.assertEqual(app.config["clients"][0]["y"], 0)
        self.assertTrue(any("Client approvato rilevato" in message for message in logs))

    def test_unknown_discovery_is_pending_without_auto_approve(self) -> None:
        import kymorem_server as server

        logs: list[str] = []
        app = server.KyMoRemApp.__new__(server.KyMoRemApp)
        app.server_active = True
        app.selected_client = ""
        app.discovered_clients = {}
        app.config = {"discovery": {"auto_connect": True, "auto_approve": False}, "clients": []}
        app.link = type("Link", (), {"connected": False, "connecting": False})()
        app._log = logs.append
        app._update_discovery_badge = lambda: None
        app._save_config = lambda: None
        app._refresh_client_list = lambda: None
        app._draw_layout = lambda: None
        app._discovery_auto_connect = lambda: True
        app._connect = mock.Mock()

        app._handle_discovery(
            (
                {
                    "type": "discovery_announce",
                    "payload": {
                        "role": "client",
                        "name": "unapproved",
                        "host": "10.0.0.91",
                        "port": 54865,
                    },
                },
                ("10.0.0.91", 54866),
            )
        )

        self.assertEqual(len(app.config["clients"]), 1)
        self.assertEqual(app.config["clients"][0]["source"], "discovery_pending")
        self.assertFalse(app.config["clients"][0]["enabled"])
        app._connect.assert_not_called()
        self.assertTrue(any("attesa di approvazione" in message for message in logs))

    def test_reserved_position_extends_along_direction_when_occupied(self) -> None:
        import kymorem_server as server

        clients = [
            {"name": "linux-iMac", "host": "10.0.0.80", "port": 54865, "x": 1, "y": 0},
        ]
        candidate = {"name": "windows7", "host": "10.0.0.49", "port": 54865, "x": 1, "y": 0}

        reserved = server.reserve_client_position(candidate, clients)

        self.assertEqual((reserved["x"], reserved["y"]), (2, 0))
        self.assertEqual(reserved["position"], "right")

    def test_client_config_skips_disabled_pending_selection(self) -> None:
        import kymorem_server as server

        app = server.KyMoRemApp.__new__(server.KyMoRemApp)
        app.selected_client = "10.8.0.2:54999"
        app.config = {
            "clients": [
                {"name": "pending", "host": "10.8.0.2", "port": 54999, "source": "discovery_pending", "enabled": False},
                {"name": "windows7", "host": "10.0.0.49", "port": 54865, "source": "manual", "enabled": True},
            ]
        }

        selected = app._client_config()

        self.assertEqual(selected["name"], "windows7")
        self.assertEqual(app.selected_client, "10.0.0.49:54865")

    def test_connect_rejects_disabled_pending_client(self) -> None:
        import kymorem_server as server

        logs: list[str] = []
        app = server.KyMoRemApp.__new__(server.KyMoRemApp)
        app.server_active = True
        app.selected_client = "10.8.0.2:54999"
        app.config = {
            "clients": [
                {"name": "pending", "host": "10.8.0.2", "port": 54999, "source": "discovery_pending", "enabled": False}
            ]
        }
        app.link = type("Link", (), {"connect": mock.Mock()})()
        app._log = logs.append
        app._refresh_server_toggle = lambda: None
        app._token_valid = lambda: True

        app._connect()

        app.link.connect.assert_not_called()
        self.assertTrue(any("non approvato" in message for message in logs))

    def test_refresh_now_reloads_config_and_skips_pending_selection(self) -> None:
        import kymorem_server as server

        logs: list[str] = []
        app = server.KyMoRemApp.__new__(server.KyMoRemApp)
        app.selected_client = "10.8.0.2:54999"
        app.server_active = True
        app.theme_id = "old_school_x11"
        app.discovered_clients = {}
        app.discovery_beacon = None
        app.discovery_listener = None
        app.engine = type("Engine", (), {"enabled": True})()
        app.link = type("Link", (), {"connected": False})()
        app._log = logs.append
        app._start_discovery = lambda: None
        app._stop_discovery = lambda: None
        app._prune_transient_clients = lambda: False
        app._refresh_server_toggle = lambda: None
        app._refresh_client_list = lambda: None
        app._update_discovery_badge = lambda: None
        app._draw_layout = lambda: None
        app._set_status = lambda *_args, **_kwargs: None
        app._apply_server_layout = lambda: None
        app.config = {"clients": []}
        loaded = {
            "language": "it",
            "theme": "old_school_x11",
            "mode": "server",
            "server_on": True,
            "clients": [
                {"name": "pending", "host": "10.8.0.2", "port": 54999, "source": "discovery_pending", "enabled": False},
                {"name": "windows7", "host": "10.0.0.49", "port": 54865, "source": "manual", "enabled": True},
            ],
        }

        with mock.patch.object(server, "load_config", return_value=loaded):
            app._refresh_now()

        self.assertEqual(app.selected_client, "10.0.0.49:54865")
        self.assertTrue(any(message == "Aggiornato." for message in logs))

    def test_refresh_now_persists_current_layout_before_reload(self) -> None:
        import kymorem_server as server

        logs: list[str] = []
        app = server.KyMoRemApp.__new__(server.KyMoRemApp)
        app.selected_client = "10.0.0.49:54865"
        app.server_active = True
        app.theme_id = "old_school_x11"
        app.discovered_clients = {}
        app.discovery_beacon = None
        app.discovery_listener = None
        app.engine = type("Engine", (), {"enabled": True})()
        app.link = type("Link", (), {"connected": False})()
        app._log = logs.append
        app._start_discovery = lambda: None
        app._stop_discovery = lambda: None
        app._prune_transient_clients = lambda: False
        app._refresh_server_toggle = lambda: None
        app._refresh_client_list = lambda: None
        app._update_discovery_badge = lambda: None
        app._draw_layout = lambda: None
        app._set_status = lambda *_args, **_kwargs: None
        app.config = {
            "language": "it",
            "theme": "old_school_x11",
            "mode": "server",
            "server_on": True,
            "clients": [
                {"name": "linux-iMac", "host": "10.0.0.80", "port": 54865, "x": -1, "y": 0, "enabled": True},
                {"name": "windows7", "host": "10.0.0.49", "port": 54865, "x": 0, "y": 1, "enabled": True},
            ],
        }

        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch.object(server, "app_dir", return_value=Path(tmp)):
                app._refresh_now()
                saved = json.loads((Path(tmp) / "config.json").read_text(encoding="utf-8"))

        self.assertEqual((saved["clients"][0]["x"], saved["clients"][0]["y"]), (-1, 0))
        self.assertEqual((saved["clients"][1]["x"], saved["clients"][1]["y"]), (0, 1))
        self.assertEqual(app.config["clients"][1]["position"], "down")
        self.assertTrue(any(message == "Aggiornato." for message in logs))

    def test_health_badge_counts_configured_clients_when_udp_discovery_is_zero(self) -> None:
        import kymorem_server as server

        class Label:
            def __init__(self) -> None:
                self.text = ""

            def winfo_exists(self) -> bool:
                return True

            def configure(self, **kwargs) -> None:
                self.text = kwargs.get("text", self.text)

        app = server.KyMoRemApp.__new__(server.KyMoRemApp)
        app.server_active = True
        app.text = server.TEXT["it"]
        app.config = {
            "discovery": {"enabled": True},
            "clients": [
                {"name": "linux-iMac", "host": "10.0.0.80", "port": 54865, "x": 1, "y": 0, "enabled": True},
                {"name": "windows7", "host": "10.0.0.49", "port": 54865, "x": 0, "y": 1, "enabled": True},
            ],
        }
        app.discovered_clients = {}
        app.discovery_badge = Label()
        app.link = type("Link", (), {"connected": False, "endpoint": None})()
        app.client_health = {
            "10.0.0.80:54865": {"state": "online", "seen": time.time(), "source": "secure_probe"},
            "10.0.0.49:54865": {"state": "online", "seen": time.time(), "source": "secure_probe"},
        }

        app._update_discovery_badge()

        self.assertIn("CLIENTI // 2/2 ONLINE // UDP 0", app.discovery_badge.text)

    def test_runtime_view_marks_secure_probe_online_client(self) -> None:
        import kymorem_server as server

        app = server.KyMoRemApp.__new__(server.KyMoRemApp)
        app.text = server.TEXT["it"]
        app.discovered_clients = {}
        app.link = type("Link", (), {"connected": False, "endpoint": None})()
        app.client_health = {"10.0.0.49:54865": {"state": "online", "seen": time.time(), "source": "secure_probe"}}

        view = app._client_runtime_view({"name": "windows7", "host": "10.0.0.49", "port": 54865, "enabled": True})

        self.assertTrue(view["online"])
        self.assertEqual(view["label"], "ONLINE")

    def test_recent_online_health_survives_one_transient_probe_failure(self) -> None:
        import kymorem_server as server

        app = server.KyMoRemApp.__new__(server.KyMoRemApp)
        app.text = server.TEXT["it"]
        app.config = {"discovery": {"enabled": True}, "clients": []}
        app.discovered_clients = {}
        app.link = type("Link", (), {"connected": False, "endpoint": None})()
        app.client_health = {"10.0.0.49:54865": {"state": "online", "seen": time.time(), "source": "secure_probe"}}
        app._update_discovery_badge = lambda: None
        app._refresh_client_list = lambda: None
        app._draw_layout = lambda: None

        app._apply_client_health(
            {
                "key": "10.0.0.49:54865",
                "host": "10.0.0.49",
                "port": 54865,
                "state": "offline",
                "source": "secure_probe",
                "detail": "temporary timeout",
                "seen": time.time(),
            }
        )

        self.assertEqual(app.client_health["10.0.0.49:54865"]["state"], "online")
        self.assertEqual(app.client_health["10.0.0.49:54865"]["last_error"], "temporary timeout")

    def test_normalize_layout_extends_overlapping_enabled_clients(self) -> None:
        import kymorem_server as server

        clients = server.normalize_layout_clients(
            [
                {"name": "linux-iMac", "host": "10.0.0.80", "port": 54865, "x": 1, "y": 0, "enabled": True},
                {"name": "windows7", "host": "10.0.0.49", "port": 54865, "x": 1, "y": 0, "enabled": True},
            ]
        )

        self.assertEqual((clients[0]["x"], clients[0]["y"]), (1, 0))
        self.assertEqual((clients[1]["x"], clients[1]["y"]), (2, 0))

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

    def test_pointer_inside_ui_is_safe_before_root_exists(self) -> None:
        import kymorem_server as server

        app = server.KyMoRemApp.__new__(server.KyMoRemApp)

        self.assertFalse(server.KyMoRemApp._pointer_inside_ui(app, 0, 0))


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
    def test_windows_subprocess_text_uses_replacement_errors(self) -> None:
        import kymorem_windows_client as client

        with mock.patch.object(client.subprocess, "run") as run:
            client.run_text_command(["netsh", "advfirewall"])

        run.assert_called_once()
        self.assertTrue(run.call_args.kwargs["text"])
        self.assertEqual(run.call_args.kwargs["errors"], "replace")

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
