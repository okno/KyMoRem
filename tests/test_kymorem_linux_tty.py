from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
PY_RUNTIME = ROOT / "runtime" / "python"
sys.path.insert(0, str(PY_RUNTIME))


class TtyClientTests(unittest.TestCase):
    def test_wheel_steps_are_capped(self) -> None:
        import kymorem_tty_client as tty

        self.assertEqual(tty.wheel_steps(0), 0)
        self.assertEqual(tty.wheel_steps(119), 0)
        self.assertEqual(tty.wheel_steps(120), 1)
        self.assertEqual(tty.wheel_steps(120 * 1000), tty.MAX_WHEEL_STEPS_PER_FRAME)

    def test_tty_surface_enter_and_move_clamp_to_terminal(self) -> None:
        import kymorem_tty_client as tty

        surface = tty.TtySurface("test-tty")
        surface.width = 80
        surface.height = 24
        with mock.patch.object(surface, "draw"):
            surface.enter("left", 0.5, 0.5)
            self.assertEqual(surface.x, 1)
            surface.move(-500, 500)
        self.assertEqual(surface.x, 1)
        self.assertEqual(surface.y, surface.height)
        self.assertEqual(surface.edge(), "left")


class LinuxServerTests(unittest.TestCase):
    def test_linux_server_normalizes_client_grid(self) -> None:
        import kymorem_linux_server as linux_server

        client = linux_server.normalize_client({"name": "tty", "position": "down"}, 0)
        self.assertEqual((client["x"], client["y"]), (0, 1))
        self.assertEqual(linux_server.client_key({"host": "10.0.0.9", "port": 54865}), "10.0.0.9:54865")


if __name__ == "__main__":
    unittest.main()
