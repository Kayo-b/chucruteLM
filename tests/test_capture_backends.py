from __future__ import annotations

import unittest
from types import SimpleNamespace

from chucrutelm.capture.linux import (
    EvdevInputObserver,
    GrimScreenCaptureBackend,
    _BaseInputObserver,
    choose_capture_backend,
    choose_input_backend,
    find_window,
    is_wayland_session,
    parse_hyprctl_clients,
    resolve_evdev_device,
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

    def test_resolve_evdev_device_prefers_keyboard_only_match(self) -> None:
        descriptions = (
            {
                "path": "/dev/input/event9",
                "name": "Corne Keyboard",
                "keyboard": True,
                "mouse": True,
                "pointer": True,
            },
            {
                "path": "/dev/input/event17",
                "name": "Corne Keyboard",
                "keyboard": True,
                "mouse": False,
                "pointer": False,
            },
        )
        resolved = resolve_evdev_device("Corne Keyboard", kind="keyboard", descriptions=descriptions)
        self.assertEqual(resolved, "/dev/input/event17")

    def test_resolve_evdev_device_prefers_pointer_mouse_match(self) -> None:
        descriptions = (
            {
                "path": "/dev/input/event4",
                "name": "Logitech G502 HERO",
                "keyboard": False,
                "mouse": True,
                "pointer": False,
            },
            {
                "path": "/dev/input/event5",
                "name": "Logitech G502 HERO",
                "keyboard": False,
                "mouse": True,
                "pointer": True,
            },
        )
        resolved = resolve_evdev_device("Logitech G502 HERO", kind="mouse", descriptions=descriptions)
        self.assertEqual(resolved, "/dev/input/event5")

    def test_resolve_evdev_device_raises_when_name_is_missing(self) -> None:
        with self.assertRaisesRegex(RuntimeError, "Available mouse devices: Logitech G502 HERO"):
            resolve_evdev_device(
                "Corne Keyboard",
                kind="mouse",
                descriptions=(
                    {
                        "path": "/dev/input/event5",
                        "name": "Logitech G502 HERO",
                        "keyboard": False,
                        "mouse": True,
                        "pointer": True,
                    },
                ),
            )

    def test_input_snapshot_drains_tapped_inputs(self) -> None:
        observer = _BaseInputObserver()
        observer._set_key("up", True)
        observer._set_button("left", True)

        first = observer.snapshot()
        self.assertEqual(first.pressed_keys, ("up",))
        self.assertEqual(first.pressed_buttons, ("left",))
        self.assertEqual(first.tapped_keys, ("up",))
        self.assertEqual(first.tapped_buttons, ("left",))

        second = observer.snapshot()
        self.assertEqual(second.pressed_keys, ("up",))
        self.assertEqual(second.pressed_buttons, ("left",))
        self.assertEqual(second.tapped_keys, ())
        self.assertEqual(second.tapped_buttons, ())

    def test_evdev_repeat_events_do_not_create_extra_taps(self) -> None:
        observer = EvdevInputObserver()
        ecodes = SimpleNamespace(
            EV_KEY=1,
            BTN_MOUSE=272,
            BTN_JOYSTICK=288,
            KEY={103: "KEY_UP"},
        )

        observer._handle_event(SimpleNamespace(type=ecodes.EV_KEY, code=103, value=1), ecodes)
        observer._handle_event(SimpleNamespace(type=ecodes.EV_KEY, code=103, value=2), ecodes)

        first = observer.snapshot()
        self.assertEqual(first.pressed_keys, ("up",))
        self.assertEqual(first.tapped_keys, ("up",))

        observer._handle_event(SimpleNamespace(type=ecodes.EV_KEY, code=103, value=0), ecodes)
        second = observer.snapshot()
        self.assertEqual(second.pressed_keys, ())
        self.assertEqual(second.tapped_keys, ())

    def test_evdev_mouse_buttons_normalize_numeric_codes(self) -> None:
        observer = EvdevInputObserver()
        ecodes = SimpleNamespace(
            EV_KEY=1,
            BTN_MOUSE=272,
            BTN_JOYSTICK=288,
            KEY={272: 272, 273: 273},
        )

        observer._handle_event(SimpleNamespace(type=ecodes.EV_KEY, code=272, value=1), ecodes)
        observer._handle_event(SimpleNamespace(type=ecodes.EV_KEY, code=273, value=1), ecodes)

        first = observer.snapshot()
        self.assertEqual(first.pressed_buttons, ("left", "right"))
        self.assertEqual(first.tapped_buttons, ("left", "right"))


if __name__ == "__main__":
    unittest.main()
