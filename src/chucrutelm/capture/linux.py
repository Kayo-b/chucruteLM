from __future__ import annotations

from dataclasses import asdict, dataclass
from io import BytesIO
import json
import os
from pathlib import Path
import select
import shutil
import subprocess
from threading import Event, Lock, Thread
import time
from typing import TYPE_CHECKING

from ..config import CaptureRegion
from ..input_names import normalize_button_name, normalize_key_name

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence
    import numpy as np


def _session_env(env: Mapping[str, str] | None = None) -> Mapping[str, str]:
    return os.environ if env is None else env


def list_evdev_device_paths() -> tuple[Path, ...]:
    return tuple(sorted(Path("/dev/input").glob("event*")))


@dataclass(frozen=True)
class LinuxWindow:
    class_name: str
    title: str
    region: CaptureRegion
    monitor: int | None = None
    workspace: str | None = None
    focus_history_id: int | None = None


def _run_command(command: Sequence[str]) -> str:
    completed = subprocess.run(command, capture_output=True, check=False, text=True)
    if completed.returncode != 0:
        stderr = completed.stderr.strip()
        raise RuntimeError(f"Command failed ({' '.join(command)}): {stderr or 'unknown error'}")
    return completed.stdout


def parse_hyprctl_clients(payload: str) -> list[LinuxWindow]:
    raw_clients = json.loads(payload)
    windows: list[LinuxWindow] = []
    for client in raw_clients:
        at = client.get("at")
        size = client.get("size")
        if not isinstance(at, list) or not isinstance(size, list) or len(at) != 2 or len(size) != 2:
            continue
        windows.append(
            LinuxWindow(
                class_name=str(client.get("class", "")),
                title=str(client.get("title", "")),
                region=CaptureRegion(int(at[0]), int(at[1]), int(size[0]), int(size[1])),
                monitor=int(client["monitor"]) if client.get("monitor") is not None else None,
                workspace=str(client.get("workspace", {}).get("name", "")) or None,
                focus_history_id=int(client["focusHistoryID"])
                if client.get("focusHistoryID") is not None
                else None,
            )
        )
    return windows


def list_open_windows(env: Mapping[str, str] | None = None) -> list[LinuxWindow]:
    current_env = _session_env(env)
    if is_wayland_session(current_env) and shutil.which("hyprctl") is not None:
        return parse_hyprctl_clients(_run_command(("hyprctl", "clients", "-j")))
    raise RuntimeError("Automatic window detection is currently supported on Hyprland/Wayland only.")


def find_window(
    *,
    class_name: str | None = None,
    title: str | None = None,
    env: Mapping[str, str] | None = None,
) -> LinuxWindow:
    wanted_class = class_name.lower() if class_name else None
    wanted_title = title.lower() if title else None
    matches: list[tuple[int, LinuxWindow]] = []
    for window in list_open_windows(env=env):
        score = 0
        current_class = window.class_name.lower()
        current_title = window.title.lower()
        if wanted_class is not None:
            if current_class == wanted_class:
                score += 4
            elif wanted_class in current_class:
                score += 2
            else:
                continue
        if wanted_title is not None:
            if current_title == wanted_title:
                score += 4
            elif wanted_title in current_title:
                score += 2
            else:
                continue
        matches.append((score, window))

    if not matches:
        detail = ", ".join(
            part
            for part in (
                f"class={class_name!r}" if class_name else "",
                f"title={title!r}" if title else "",
            )
            if part
        ) or "the requested selector"
        raise RuntimeError(f"No open window matched {detail}.")

    matches.sort(
        key=lambda item: (
            -item[0],
            item[1].focus_history_id if item[1].focus_history_id is not None else 10**9,
            item[1].title,
        )
    )
    return matches[0][1]


def resolve_capture_region(
    *,
    left: int | None,
    top: int | None,
    width: int | None,
    height: int | None,
    window_class: str | None = None,
    window_title: str | None = None,
    env: Mapping[str, str] | None = None,
) -> CaptureRegion:
    values = (left, top, width, height)
    if all(value is not None for value in values):
        return CaptureRegion(int(left), int(top), int(width), int(height))
    if any(value is not None for value in values):
        raise RuntimeError("Region arguments must all be provided together.")
    if window_class is None and window_title is None:
        raise RuntimeError("No capture region or window selector was provided.")
    return find_window(class_name=window_class, title=window_title, env=env).region


def describe_evdev_devices() -> list[dict[str, object]]:
    try:
        from evdev import InputDevice, ecodes
    except ImportError:
        return [{"path": str(path)} for path in list_evdev_device_paths()]

    descriptions: list[dict[str, object]] = []
    for path in list_evdev_device_paths():
        entry: dict[str, object] = {"path": str(path)}
        try:
            device = InputDevice(str(path))
            capabilities = device.capabilities()
        except OSError as exc:
            entry["error"] = str(exc)
            descriptions.append(entry)
            continue

        key_codes = set(capabilities.get(ecodes.EV_KEY, ()))
        has_keyboard = any(code < ecodes.BTN_MISC for code in key_codes)
        has_mouse_buttons = any(ecodes.BTN_MOUSE <= code < ecodes.BTN_JOYSTICK for code in key_codes)
        has_pointer_motion = ecodes.EV_REL in capabilities or ecodes.EV_ABS in capabilities
        entry.update(
            {
                "name": device.name,
                "keyboard": has_keyboard,
                "mouse": has_mouse_buttons,
                "pointer": has_pointer_motion,
            }
        )
        device.close()
        descriptions.append(entry)
    return descriptions


def resolve_evdev_device(
    device_name: str,
    *,
    kind: str,
    descriptions: Sequence[Mapping[str, object]] | None = None,
) -> str:
    if kind not in {"keyboard", "mouse"}:
        raise ValueError(f"Unsupported evdev device kind: {kind}")

    available = list(describe_evdev_devices() if descriptions is None else descriptions)
    exact_name_matches = [entry for entry in available if entry.get("name") == device_name]
    candidates = [entry for entry in exact_name_matches if entry.get(kind)]
    if not candidates:
        available_names = sorted(
            {
                str(entry["name"])
                for entry in available
                if entry.get("name") is not None and entry.get(kind)
            }
        )
        available_label = ", ".join(available_names) if available_names else "none"
        raise RuntimeError(
            f"Unable to find a readable {kind} device named {device_name!r}. "
            f"Available {kind} devices: {available_label}."
        )

    def candidate_score(entry: Mapping[str, object]) -> tuple[int, str]:
        path = str(entry["path"])
        score = 0
        if kind == "keyboard":
            if entry.get("keyboard"):
                score += 4
            if not entry.get("mouse"):
                score += 2
            if not entry.get("pointer"):
                score += 1
        else:
            if entry.get("mouse"):
                score += 4
            if entry.get("pointer"):
                score += 2
            if not entry.get("keyboard"):
                score += 1
        return (score, path)

    best_match = max(candidates, key=candidate_score)
    return str(best_match["path"])


def is_wayland_session(env: Mapping[str, str] | None = None) -> bool:
    current_env = _session_env(env)
    if current_env.get("HYPRLAND_INSTANCE_SIGNATURE"):
        return True
    if current_env.get("WAYLAND_DISPLAY"):
        return True
    if current_env.get("XDG_SESSION_TYPE", "").lower() == "wayland":
        return True
    desktop = current_env.get("XDG_CURRENT_DESKTOP", "").lower()
    return "hyprland" in desktop or "wayland" in desktop


def choose_capture_backend(
    backend: str = "auto",
    *,
    env: Mapping[str, str] | None = None,
    grim_available: bool | None = None,
) -> str:
    normalized = backend.strip().lower()
    if normalized in {"mss", "x11"}:
        return "mss"
    if normalized in {"grim", "hyprland", "wayland"}:
        return "grim"
    if normalized != "auto":
        raise ValueError(f"Unsupported capture backend: {backend}")

    if is_wayland_session(env):
        has_grim = shutil.which("grim") is not None if grim_available is None else grim_available
        if not has_grim:
            raise RuntimeError(
                "Wayland/Hyprland capture requires grim to be installed and available on PATH."
            )
        return "grim"
    return "mss"


def choose_input_backend(
    backend: str = "auto",
    *,
    env: Mapping[str, str] | None = None,
    evdev_available: bool | None = None,
    pynput_available: bool | None = None,
) -> str:
    normalized = backend.strip().lower()
    if normalized in {"evdev", "hyprland", "wayland"}:
        return "evdev"
    if normalized in {"pynput", "x11"}:
        return "pynput"
    if normalized != "auto":
        raise ValueError(f"Unsupported input backend: {backend}")

    if evdev_available is None:
        try:
            import evdev  # noqa: F401
        except ImportError:
            evdev_available = False
        else:
            evdev_available = True
    if pynput_available is None:
        try:
            import pynput  # noqa: F401
        except ImportError:
            pynput_available = False
        else:
            pynput_available = True

    if is_wayland_session(env):
        if evdev_available:
            return "evdev"
        raise RuntimeError(
            "Wayland/Hyprland input capture requires python-evdev and access to /dev/input/event*."
        )

    if pynput_available:
        return "pynput"
    if evdev_available:
        return "evdev"
    raise RuntimeError("No supported Linux input backend is available.")


@dataclass
class CapturedFrame:
    timestamp: float
    region: CaptureRegion
    rgb: np.ndarray
    grayscale: np.ndarray


@dataclass
class InputSnapshot:
    timestamp: float
    pressed_keys: tuple[str, ...]
    pressed_buttons: tuple[str, ...]
    tapped_keys: tuple[str, ...] = ()
    tapped_buttons: tuple[str, ...] = ()
    pointer_x: int = 0
    pointer_y: int = 0
    scroll_x: int = 0
    scroll_y: int = 0

    def to_record(self) -> dict[str, object]:
        return asdict(self)


class MssScreenCaptureBackend:
    def __init__(self, region: CaptureRegion) -> None:
        self.region = region
        try:
            import mss
        except ImportError as exc:
            raise RuntimeError("mss is required for X11 screen capture.") from exc
        self._mss = mss.mss()

    def capture(self) -> CapturedFrame:
        import numpy as np
        from PIL import Image

        shot = self._mss.grab(self.region.as_mss_region())
        image = Image.frombytes("RGB", shot.size, shot.rgb)
        rgb = np.asarray(image, dtype=np.uint8)
        gray = np.asarray(image.convert("L"), dtype=np.uint8)
        return CapturedFrame(timestamp=time.time(), region=self.region, rgb=rgb, grayscale=gray)


class GrimScreenCaptureBackend:
    def __init__(self, region: CaptureRegion) -> None:
        self.region = region
        self._grim_path = shutil.which("grim")
        if self._grim_path is None:
            raise RuntimeError("grim is required for Wayland/Hyprland screen capture.")

    @staticmethod
    def geometry(region: CaptureRegion) -> str:
        return f"{region.left},{region.top} {region.width}x{region.height}"

    def capture(self) -> CapturedFrame:
        import numpy as np
        from PIL import Image

        command = [
            self._grim_path,
            "-g",
            self.geometry(self.region),
            "-t",
            "png",
            "-",
        ]
        completed = subprocess.run(command, capture_output=True, check=False)
        if completed.returncode != 0:
            stderr = completed.stderr.decode("utf-8", errors="replace").strip()
            raise RuntimeError(f"grim capture failed: {stderr or 'unknown error'}")
        image = Image.open(BytesIO(completed.stdout)).convert("RGB")
        rgb = np.asarray(image, dtype=np.uint8)
        gray = np.asarray(image.convert("L"), dtype=np.uint8)
        return CapturedFrame(timestamp=time.time(), region=self.region, rgb=rgb, grayscale=gray)


class ScreenCaptureBackend:
    def __init__(self, region: CaptureRegion, backend: str = "auto") -> None:
        self.region = region
        self.backend_name = choose_capture_backend(backend)
        if self.backend_name == "grim":
            self._backend = GrimScreenCaptureBackend(region)
        else:
            self._backend = MssScreenCaptureBackend(region)

    def capture(self) -> CapturedFrame:
        return self._backend.capture()


class _BaseInputObserver:
    def __init__(self) -> None:
        self._lock = Lock()
        self._pressed_keys: set[str] = set()
        self._pressed_buttons: set[str] = set()
        self._tapped_keys: list[str] = []
        self._tapped_buttons: list[str] = []
        self._pointer_x = 0
        self._pointer_y = 0
        self._scroll_x = 0
        self._scroll_y = 0

    def snapshot(self) -> InputSnapshot:
        with self._lock:
            tapped_keys = tuple(self._tapped_keys)
            tapped_buttons = tuple(self._tapped_buttons)
            self._tapped_keys.clear()
            self._tapped_buttons.clear()
            return InputSnapshot(
                timestamp=time.time(),
                pressed_keys=tuple(sorted(self._pressed_keys)),
                pressed_buttons=tuple(sorted(self._pressed_buttons)),
                tapped_keys=tapped_keys,
                tapped_buttons=tapped_buttons,
                pointer_x=self._pointer_x,
                pointer_y=self._pointer_y,
                scroll_x=self._scroll_x,
                scroll_y=self._scroll_y,
            )

    def _set_key(self, name: str, pressed: bool) -> None:
        with self._lock:
            if pressed:
                self._pressed_keys.add(name)
                self._tapped_keys.append(name)
            else:
                self._pressed_keys.discard(name)

    def _set_button(self, name: str, pressed: bool) -> None:
        with self._lock:
            if pressed:
                self._pressed_buttons.add(name)
                self._tapped_buttons.append(name)
            else:
                self._pressed_buttons.discard(name)

    def _set_pointer(self, x: int | None = None, y: int | None = None) -> None:
        with self._lock:
            if x is not None:
                self._pointer_x = x
            if y is not None:
                self._pointer_y = y

    def _move_pointer(self, dx: int = 0, dy: int = 0) -> None:
        with self._lock:
            self._pointer_x += dx
            self._pointer_y += dy

    def _scroll_pointer(self, dx: int = 0, dy: int = 0) -> None:
        with self._lock:
            self._scroll_x += dx
            self._scroll_y += dy


class PynputInputObserver(_BaseInputObserver):
    def __init__(self) -> None:
        super().__init__()
        self._keyboard_listener = None
        self._mouse_listener = None

    def start(self) -> None:
        try:
            from pynput import keyboard, mouse
        except ImportError as exc:
            raise RuntimeError("pynput is required for X11 keyboard and mouse capture.") from exc

        self._keyboard_listener = keyboard.Listener(
            on_press=self._on_press,
            on_release=self._on_release,
        )
        self._mouse_listener = mouse.Listener(
            on_move=self._on_move,
            on_click=self._on_click,
            on_scroll=self._on_scroll,
        )
        self._keyboard_listener.start()
        self._mouse_listener.start()

    def stop(self) -> None:
        if self._keyboard_listener is not None:
            self._keyboard_listener.stop()
        if self._mouse_listener is not None:
            self._mouse_listener.stop()

    def _on_press(self, key: object) -> None:
        self._set_key(self._normalize_key(key), pressed=True)

    def _on_release(self, key: object) -> None:
        self._set_key(self._normalize_key(key), pressed=False)

    def _on_move(self, x: int, y: int) -> None:
        self._set_pointer(x=x, y=y)

    def _on_click(self, x: int, y: int, button: object, pressed: bool) -> None:
        self._set_pointer(x=x, y=y)
        self._set_button(self._normalize_button(button), pressed=pressed)

    def _on_scroll(self, x: int, y: int, dx: int, dy: int) -> None:
        self._set_pointer(x=x, y=y)
        self._scroll_pointer(dx=dx, dy=dy)

    @staticmethod
    def _normalize_key(key: object) -> str:
        if hasattr(key, "char") and key.char is not None:
            return normalize_key_name(key.char)
        key_text = str(key).lower()
        return normalize_key_name(key_text)

    @staticmethod
    def _normalize_button(button: object) -> str:
        return normalize_button_name(button)


class EvdevInputObserver(_BaseInputObserver):
    def __init__(self, device_paths: Sequence[str] | None = None) -> None:
        super().__init__()
        self.device_paths = tuple(device_paths or ())
        self._devices: list[object] = []
        self._poll_thread: Thread | None = None
        self._stop_event = Event()

    def start(self) -> None:
        try:
            from evdev import InputDevice, ecodes
        except ImportError as exc:
            raise RuntimeError("python-evdev is required for Wayland/Hyprland input capture.") from exc

        self._devices = self._open_devices(InputDevice, ecodes)
        if not self._devices:
            raise RuntimeError(self._build_unreadable_device_message())

        self._stop_event.clear()
        self._poll_thread = Thread(target=self._poll_devices, daemon=True)
        self._poll_thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        for device in self._devices:
            try:
                device.close()
            except OSError:
                pass
        if self._poll_thread is not None:
            self._poll_thread.join(timeout=1.0)
        self._devices = []

    def _open_devices(self, input_device: object, ecodes: object) -> list[object]:
        resolved_paths = [Path(path) for path in self.device_paths] if self.device_paths else list_evdev_device_paths()
        devices: list[object] = []
        for path in resolved_paths:
            try:
                device = input_device(str(path))
                capabilities = device.capabilities()
            except OSError:
                if self.device_paths:
                    raise RuntimeError(f"Unable to open input device {path}")
                continue
            if self.device_paths or self._is_relevant_device(capabilities, ecodes):
                devices.append(device)
            else:
                device.close()
        return devices

    def _build_unreadable_device_message(self) -> str:
        available_paths = [Path(path) for path in self.device_paths] if self.device_paths else list_evdev_device_paths()
        if not available_paths:
            return "No /dev/input/event* devices were found."
        if self.device_paths:
            listed = ", ".join(str(path) for path in available_paths)
            return (
                f"No readable evdev devices matched the requested paths ({listed}). "
                "Ensure the user can read those device files."
            )
        listed = ", ".join(str(path) for path in available_paths[:6])
        if len(available_paths) > 6:
            listed += ", ..."
        return (
            "No readable keyboard or mouse evdev devices were found. "
            f"Detected event devices: {listed}. "
            "Ensure the user can read /dev/input/event* (for example via the input group or a logind ACL)."
        )

    @staticmethod
    def _is_relevant_device(capabilities: Mapping[int, object], ecodes: object) -> bool:
        key_codes = set(capabilities.get(ecodes.EV_KEY, ()))
        has_keyboard_keys = any(code < ecodes.BTN_MISC for code in key_codes)
        has_mouse_buttons = any(ecodes.BTN_MOUSE <= code < ecodes.BTN_JOYSTICK for code in key_codes)
        has_pointer_motion = ecodes.EV_REL in capabilities or ecodes.EV_ABS in capabilities
        return has_keyboard_keys or has_mouse_buttons or has_pointer_motion

    def _poll_devices(self) -> None:
        from evdev import ecodes

        while not self._stop_event.is_set():
            try:
                ready, _, _ = select.select(self._devices, [], [], 0.1)
            except (OSError, ValueError):
                break
            for device in ready:
                try:
                    for event in device.read():
                        self._handle_event(event, ecodes)
                except OSError:
                    continue

    def _handle_event(self, event: object, ecodes: object) -> None:
        if event.type == ecodes.EV_KEY:
            if event.value == 2:
                return
            if ecodes.BTN_MOUSE <= event.code < ecodes.BTN_JOYSTICK:
                name = normalize_button_name(ecodes.KEY.get(event.code, event.code))
                self._set_button(name, pressed=event.value != 0)
            else:
                name = normalize_key_name(ecodes.KEY.get(event.code, f"key_{event.code}"))
                self._set_key(name, pressed=event.value != 0)
            return

        if event.type == ecodes.EV_REL:
            if event.code == ecodes.REL_X:
                self._move_pointer(dx=int(event.value))
            elif event.code == ecodes.REL_Y:
                self._move_pointer(dy=int(event.value))
            elif event.code == ecodes.REL_HWHEEL:
                self._scroll_pointer(dx=int(event.value))
            elif event.code == ecodes.REL_WHEEL:
                self._scroll_pointer(dy=int(event.value))
            return

        if event.type == ecodes.EV_ABS:
            if event.code == ecodes.ABS_X:
                self._set_pointer(x=int(event.value))
            elif event.code == ecodes.ABS_Y:
                self._set_pointer(y=int(event.value))

class LinuxInputObserver:
    def __init__(self, backend: str = "auto", device_paths: Sequence[str] | None = None) -> None:
        self.backend_name = choose_input_backend(backend)
        if self.backend_name == "evdev":
            self._backend = EvdevInputObserver(device_paths=device_paths)
        else:
            self._backend = PynputInputObserver()

    def start(self) -> None:
        self._backend.start()

    def stop(self) -> None:
        self._backend.stop()

    def snapshot(self) -> InputSnapshot:
        return self._backend.snapshot()
