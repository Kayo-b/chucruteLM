from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
import time
from typing import Protocol

from ..config import CaptureRegion
from ..input_names import normalize_button_name, normalize_key_name
from ..profiles import GameProfile

_KEY_ALIASES = {
    "backspace": "KEY_BACKSPACE",
    "caps_lock": "KEY_CAPSLOCK",
    "cmd_l": "KEY_LEFTMETA",
    "cmd_r": "KEY_RIGHTMETA",
    "ctrl_l": "KEY_LEFTCTRL",
    "ctrl_r": "KEY_RIGHTCTRL",
    "delete": "KEY_DELETE",
    "down": "KEY_DOWN",
    "end": "KEY_END",
    "enter": "KEY_ENTER",
    "esc": "KEY_ESC",
    "home": "KEY_HOME",
    "left": "KEY_LEFT",
    "page_down": "KEY_PAGEDOWN",
    "page_up": "KEY_PAGEUP",
    "right": "KEY_RIGHT",
    "shift_l": "KEY_LEFTSHIFT",
    "shift_r": "KEY_RIGHTSHIFT",
    "space": "KEY_SPACE",
    "tab": "KEY_TAB",
    "up": "KEY_UP",
    "alt_l": "KEY_LEFTALT",
    "alt_r": "KEY_RIGHTALT",
}

_BUTTON_ALIASES = {
    "left": "BTN_LEFT",
    "right": "BTN_RIGHT",
    "middle": "BTN_MIDDLE",
    "side": "BTN_SIDE",
    "extra": "BTN_EXTRA",
}


def key_name_to_linux_code(key_name: str) -> int:
    from evdev import ecodes

    normalized = normalize_key_name(key_name)
    code_name = _KEY_ALIASES.get(normalized, f"KEY_{normalized.upper()}")
    if not hasattr(ecodes, code_name):
        raise ValueError(f"Unsupported Linux key name: {key_name}")
    return int(getattr(ecodes, code_name))


def button_name_to_linux_code(button_name: str) -> int:
    from evdev import ecodes

    normalized = normalize_button_name(button_name)
    code_name = _BUTTON_ALIASES.get(normalized, f"BTN_{normalized.upper()}")
    if not hasattr(ecodes, code_name):
        raise ValueError(f"Unsupported Linux button name: {button_name}")
    return int(getattr(ecodes, code_name))


class ActionOutputBackend(Protocol):
    def press_key(self, key_name: str) -> None: ...

    def release_key(self, key_name: str) -> None: ...

    def press_button(self, button_name: str) -> None: ...

    def release_button(self, button_name: str) -> None: ...

    def move_pointer_rel(self, dx: int, dy: int) -> None: ...

    def close(self) -> None: ...


class NoopActionBackend:
    def press_key(self, key_name: str) -> None:
        del key_name

    def release_key(self, key_name: str) -> None:
        del key_name

    def press_button(self, button_name: str) -> None:
        del button_name

    def release_button(self, button_name: str) -> None:
        del button_name

    def move_pointer_rel(self, dx: int, dy: int) -> None:
        del dx, dy

    def close(self) -> None:
        return None


class UinputActionBackend:
    def __init__(
        self,
        key_names: set[str],
        button_names: set[str],
        *,
        device_name: str = "chucrutelm-virtual-input",
    ) -> None:
        try:
            from evdev import UInput, ecodes
        except ImportError as exc:
            raise RuntimeError("python-evdev is required for Linux action emission.") from exc

        codes = sorted(
            {key_name_to_linux_code(name) for name in key_names}
            | {button_name_to_linux_code(name) for name in button_names}
        )
        capabilities = {ecodes.EV_REL: [ecodes.REL_X, ecodes.REL_Y]}
        if codes:
            capabilities[ecodes.EV_KEY] = codes
        try:
            self._ui = UInput(capabilities, name=device_name)
        except OSError as exc:
            raise RuntimeError(
                "Unable to create a Linux uinput device. Ensure /dev/uinput exists and is writable."
            ) from exc
        self._ecodes = ecodes

    @classmethod
    def from_profile(
        cls,
        profile: GameProfile,
        *,
        device_name: str = "chucrutelm-virtual-input",
    ) -> "UinputActionBackend":
        key_names: set[str] = set()
        button_names: set[str] = set()
        for action_name in profile.action_space.names:
            key_names.update(profile.held_keys_for_action(action_name))
            key_names.update(profile.tapped_keys_for_action(action_name))
            button_names.update(profile.clicked_buttons_for_action(action_name))
        return cls(key_names, button_names, device_name=device_name)

    def press_key(self, key_name: str) -> None:
        self._write_key_event(key_name_to_linux_code(key_name), 1)

    def release_key(self, key_name: str) -> None:
        self._write_key_event(key_name_to_linux_code(key_name), 0)

    def press_button(self, button_name: str) -> None:
        self._write_key_event(button_name_to_linux_code(button_name), 1)

    def release_button(self, button_name: str) -> None:
        self._write_key_event(button_name_to_linux_code(button_name), 0)

    def move_pointer_rel(self, dx: int, dy: int) -> None:
        self._ui.write(self._ecodes.EV_REL, self._ecodes.REL_X, dx)
        self._ui.write(self._ecodes.EV_REL, self._ecodes.REL_Y, dy)
        self._ui.syn()

    def close(self) -> None:
        self._ui.close()

    def _write_key_event(self, code: int, value: int) -> None:
        self._ui.write(self._ecodes.EV_KEY, code, value)
        self._ui.syn()


@dataclass(frozen=True)
class ExecutedAction:
    action_name: str
    held_keys: tuple[str, ...]
    tapped_keys: tuple[str, ...]
    clicked_buttons: tuple[str, ...]
    pointer_target: tuple[int, int] | None = None


class ActionExecutor:
    def __init__(
        self,
        profile: GameProfile,
        backend: ActionOutputBackend,
        *,
        key_press_s: float = 0.05,
        key_repeat_s: float = 0.2,
        button_press_s: float = 0.05,
        button_repeat_s: float = 0.2,
        pointer_repeat_s: float | None = None,
        initial_pointer_position: tuple[int, int] | None = None,
        time_fn: Callable[[], float] = time.monotonic,
        sleep_fn: Callable[[float], None] = time.sleep,
    ) -> None:
        self.profile = profile
        self.backend = backend
        self.key_press_s = key_press_s
        self.key_repeat_s = key_repeat_s
        self.button_press_s = button_press_s
        self.button_repeat_s = button_repeat_s
        self.pointer_repeat_s = button_repeat_s if pointer_repeat_s is None else pointer_repeat_s
        self._time_fn = time_fn
        self._sleep_fn = sleep_fn
        self._held_keys: set[str] = set()
        self._last_action_name: str | None = None
        self._last_key_emit: dict[str, float] = {}
        self._last_button_emit: dict[str, float] = {}
        self._last_pointer_emit: dict[str, float] = {}
        self._pointer_position = initial_pointer_position

    def apply(
        self,
        action_name: str,
        *,
        capture_region: CaptureRegion | None = None,
    ) -> ExecutedAction:
        target_hold_keys = set(self.profile.held_keys_for_action(action_name))
        target_tap_keys = tuple(sorted(set(self.profile.tapped_keys_for_action(action_name))))
        target_buttons = tuple(sorted(set(self.profile.clicked_buttons_for_action(action_name))))
        tapped_keys: list[str] = []
        clicked_buttons: list[str] = []
        pointer_target: tuple[int, int] | None = None

        for key_name in sorted(self._held_keys - target_hold_keys):
            self.backend.release_key(key_name)
        for key_name in sorted(target_hold_keys - self._held_keys):
            self.backend.press_key(key_name)
        self._held_keys = target_hold_keys

        now = self._time_fn()
        if target_tap_keys:
            last_emit = max((self._last_key_emit.get(key_name, float("-inf")) for key_name in target_tap_keys))
            if self._last_action_name != action_name or now - last_emit >= self.key_repeat_s:
                for key_name in target_tap_keys:
                    self.backend.press_key(key_name)
                self._sleep_fn(self.key_press_s)
                for key_name in reversed(target_tap_keys):
                    self.backend.release_key(key_name)
                    self._last_key_emit[key_name] = now
                tapped_keys.extend(target_tap_keys)

        for button_name in target_buttons:
            last_emit = self._last_button_emit.get(button_name)
            if self._last_action_name != action_name or last_emit is None or now - last_emit >= self.button_repeat_s:
                self.backend.press_button(button_name)
                self._sleep_fn(self.button_press_s)
                self.backend.release_button(button_name)
                self._last_button_emit[button_name] = now
                clicked_buttons.append(button_name)

        if capture_region is not None:
            pointer_action = self.profile.resolve_pointer_action(action_name, capture_region)
        else:
            pointer_action = None
        if pointer_action is not None:
            last_emit = self._last_pointer_emit.get(action_name)
            if self._last_action_name != action_name or last_emit is None or now - last_emit >= self.pointer_repeat_s:
                if self._pointer_position is None:
                    raise RuntimeError(
                        "Pointer action execution requires an initial pointer position. "
                        "Provide one when constructing the action executor."
                    )
                pointer_target = pointer_action.pointer_target
                dx = pointer_target[0] - self._pointer_position[0]
                dy = pointer_target[1] - self._pointer_position[1]
                if dx != 0 or dy != 0:
                    self.backend.move_pointer_rel(dx, dy)
                self.backend.press_button(pointer_action.button)
                self._sleep_fn(self.button_press_s)
                self.backend.release_button(pointer_action.button)
                self._pointer_position = pointer_target
                self._last_pointer_emit[action_name] = now
                clicked_buttons.append(pointer_action.button)

        self._last_action_name = action_name
        return ExecutedAction(
            action_name=action_name,
            held_keys=tuple(sorted(self._held_keys)),
            tapped_keys=tuple(tapped_keys),
            clicked_buttons=tuple(clicked_buttons),
            pointer_target=pointer_target,
        )

    def release_all(self) -> None:
        for key_name in sorted(self._held_keys):
            self.backend.release_key(key_name)
        self._held_keys.clear()
        self._last_action_name = None

    def close(self) -> None:
        self.release_all()
        self.backend.close()
