from __future__ import annotations

from collections.abc import Iterable

_KEY_ALIASES = {
    "esc": "esc",
    "return": "enter",
    "kpenter": "enter",
    "pagedown": "page_down",
    "pageup": "page_up",
    "capslock": "caps_lock",
    "leftctrl": "ctrl_l",
    "rightctrl": "ctrl_r",
    "leftalt": "alt_l",
    "rightalt": "alt_r",
    "leftshift": "shift_l",
    "rightshift": "shift_r",
    "leftmeta": "cmd_l",
    "rightmeta": "cmd_r",
}

_BUTTON_ALIASES = {
    "left": "left",
    "right": "right",
    "middle": "middle",
    "side": "side",
    "extra": "extra",
    "forward": "extra",
    "back": "side",
}

_BUTTON_CODE_ALIASES = {
    "272": "left",
    "273": "right",
    "274": "middle",
    "275": "side",
    "276": "extra",
    "277": "forward",
    "278": "back",
    "279": "task",
}


def _normalize_text(name: object) -> str:
    return str(name).strip().lower().replace("key.", "").replace("button.", "")


def normalize_key_name(name: object) -> str:
    normalized = _normalize_text(name)
    if normalized.startswith("key_"):
        normalized = normalized[4:]
    return _KEY_ALIASES.get(normalized, normalized)


def normalize_button_name(name: object) -> str:
    normalized = _normalize_text(name)
    normalized = _BUTTON_CODE_ALIASES.get(normalized, normalized)
    if normalized.startswith("btn_"):
        normalized = normalized[4:]
    return _BUTTON_ALIASES.get(normalized, normalized)


def normalize_key_names(names: Iterable[object]) -> tuple[str, ...]:
    return tuple(normalize_key_name(name) for name in names)


def normalize_button_names(names: Iterable[object]) -> tuple[str, ...]:
    return tuple(normalize_button_name(name) for name in names)
