from __future__ import annotations

import unittest

from chucrutelm.capture.linux import (
    GrimScreenCaptureBackend,
    choose_capture_backend,
    choose_input_backend,
    find_window,
    is_wayland_session,
    parse_hyprctl_clients,
    resolve_capture_region,
)
from chucrutelm.config import CaptureRegion


class CaptureBackendSelectionTest(unittest.TestCase):
    HYPR_CLIENTS = """[
      {
        "class": "org.gnome.Nautilus",
        "title": "Tibia",
        "at": [649, 737],
        "size": [627, 691],
        "monitor": 1,
        "workspace": {"name": "1"},
        "focusHistoryID": 2
      },
      {
        "class": "com.tibia.client",
        "title": "Tibia",
        "at": [22, 152],
        "size": [1300, 900],
        "monitor": 1,
        "workspace": {"name": "1"},
        "focusHistoryID": 1
      }
    ]"""

    def test_is_wayland_session_detects_hyprland(self) -> None:
        self.assertTrue(is_wayland_session({"HYPRLAND_INSTANCE_SIGNATURE": "abc"}))

    def test_choose_capture_backend_uses_grim_on_wayland(self) -> None:
        backend = choose_capture_backend(
            "auto",
            env={"WAYLAND_DISPLAY": "wayland-1"},
            grim_available=True,
        )
        self.assertEqual(backend, "grim")

    def test_choose_capture_backend_uses_mss_on_x11(self) -> None:
        backend = choose_capture_backend(
            "auto",
            env={"DISPLAY": ":0", "XDG_SESSION_TYPE": "x11"},
        )
        self.assertEqual(backend, "mss")

    def test_choose_input_backend_prefers_evdev_on_wayland(self) -> None:
        backend = choose_input_backend(
            "auto",
            env={"XDG_SESSION_TYPE": "wayland"},
            evdev_available=True,
            pynput_available=True,
        )
        self.assertEqual(backend, "evdev")

    def test_choose_input_backend_prefers_pynput_on_x11(self) -> None:
        backend = choose_input_backend(
            "auto",
            env={"DISPLAY": ":0", "XDG_SESSION_TYPE": "x11"},
            evdev_available=True,
            pynput_available=True,
        )
        self.assertEqual(backend, "pynput")

    def test_grim_geometry_matches_region(self) -> None:
        geometry = GrimScreenCaptureBackend.geometry(CaptureRegion(10, 20, 1280, 720))
        self.assertEqual(geometry, "10,20 1280x720")

    def test_parse_hyprctl_clients_extracts_windows(self) -> None:
        windows = parse_hyprctl_clients(self.HYPR_CLIENTS)
        self.assertEqual(len(windows), 2)
        self.assertEqual(windows[1].class_name, "com.tibia.client")
        self.assertEqual(windows[1].region, CaptureRegion(22, 152, 1300, 900))

    def test_find_window_prefers_exact_class_match(self) -> None:
        from unittest.mock import patch

        with patch("chucrutelm.capture.linux.list_open_windows", return_value=parse_hyprctl_clients(self.HYPR_CLIENTS)):
            window = find_window(class_name="com.tibia.client", title="Tibia")
        self.assertEqual(window.class_name, "com.tibia.client")
        self.assertEqual(window.region, CaptureRegion(22, 152, 1300, 900))

    def test_resolve_capture_region_uses_window_selectors(self) -> None:
        from unittest.mock import patch

        with patch("chucrutelm.capture.linux.find_window") as mock_find_window:
            mock_find_window.return_value.region = CaptureRegion(22, 152, 1300, 900)
            region = resolve_capture_region(
                left=None,
                top=None,
                width=None,
                height=None,
                window_class="com.tibia.client",
                window_title="Tibia",
            )
        self.assertEqual(region, CaptureRegion(22, 152, 1300, 900))


if __name__ == "__main__":
    unittest.main()
