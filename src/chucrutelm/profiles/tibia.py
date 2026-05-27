from __future__ import annotations

from collections.abc import Iterable, Sequence

from .base import GameProfile

TIBIA_ACTIONS: tuple[str, ...] = (
    "noop",
    "move_up",
    "move_down",
    "move_left",
    "move_right",
    "move_up_left",
    "move_up_right",
    "move_down_left",
    "move_down_right",
    "next_target",
    "attack_interact",
    "context_use",
    "hotkey_f1",
    "hotkey_f2",
    "hotkey_f3",
    "hotkey_f4",
    "hotkey_f5",
    "hotkey_f6",
    "hotkey_f7",
    "hotkey_f8",
    "hotkey_f9",
    "hotkey_f10",
    "hotkey_f11",
    "hotkey_f12",
    "open_hotkeys",
    "open_vip_list",
    "open_battle_list",
    "open_skills_window",
    "open_spell_list",
    "open_questlog",
    "stop_actions",
    "logout",
    "switch_character",
    "toggle_fullscreen",
    "next_chat_channel",
    "previous_chat_channel",
)

TIBIA_WINDOW_CLASS = "com.tibia.client"
TIBIA_WINDOW_TITLE = "Tibia"

TIBIA_KEY_BINDINGS: dict[str, tuple[tuple[str, ...], ...]] = {
    "move_up": (("up",), ("w",)),
    "move_down": (("down",), ("s",)),
    "move_left": (("left",), ("a",)),
    "move_right": (("right",), ("d",)),
    "move_up_left": (("kp7",), ("home",)),
    "move_up_right": (("kp9",), ("page_up",)),
    "move_down_left": (("kp1",), ("end",)),
    "move_down_right": (("kp3",), ("page_down",)),
    "next_target": (("space",),),
    "hotkey_f1": (("f1",),),
    "hotkey_f2": (("f2",),),
    "hotkey_f3": (("f3",),),
    "hotkey_f4": (("f4",),),
    "hotkey_f5": (("f5",),),
    "hotkey_f6": (("f6",),),
    "hotkey_f7": (("f7",),),
    "hotkey_f8": (("f8",),),
    "hotkey_f9": (("f9",),),
    "hotkey_f10": (("f10",),),
    "hotkey_f11": (("f11",),),
    "hotkey_f12": (("f12",),),
    "open_hotkeys": (("ctrl_l", "k"),),
    "open_vip_list": (("ctrl_l", "p"),),
    "open_battle_list": (("ctrl_l", "b"),),
    "open_skills_window": (("ctrl_l", "s"),),
    "open_spell_list": (("alt_l", "s"),),
    "open_questlog": (("ctrl_l", "u"),),
    "stop_actions": (("esc",),),
    "logout": (("ctrl_l", "q"),),
    "switch_character": (("ctrl_l", "g"),),
    "toggle_fullscreen": (("alt_l", "enter"),),
    "next_chat_channel": (("tab",),),
    "previous_chat_channel": (("shift_l", "tab"),),
}

TIBIA_BUTTON_BINDINGS: dict[str, tuple[tuple[str, ...], ...]] = {
    "attack_interact": (("left",),),
    "context_use": (("right",),),
}

TIBIA_TAPPED_KEY_ACTIONS: frozenset[str] = frozenset(
    action_name for action_name in TIBIA_ACTIONS if action_name in TIBIA_KEY_BINDINGS
)
TIBIA_CLICKED_BUTTON_ACTIONS: frozenset[str] = frozenset(TIBIA_BUTTON_BINDINGS)


def _merge_bindings(
    defaults: dict[str, tuple[tuple[str, ...], ...]],
    overrides: dict[str, tuple[tuple[str, ...], ...]] | None,
) -> dict[str, tuple[tuple[str, ...], ...]]:
    merged = dict(defaults)
    if overrides:
        merged.update(overrides)
    return merged


def tibia_default_action_names() -> tuple[str, ...]:
    return TIBIA_ACTIONS


def build_tibia_profile(
    action_names: Sequence[str] | None = None,
    *,
    key_bindings: dict[str, tuple[tuple[str, ...], ...]] | None = None,
    button_bindings: dict[str, tuple[tuple[str, ...], ...]] | None = None,
) -> GameProfile:
    selected_actions = tuple(action_names or TIBIA_ACTIONS)
    selected_action_names = frozenset(selected_actions)
    merged_keys = {
        name: values
        for name, values in _merge_bindings(TIBIA_KEY_BINDINGS, key_bindings).items()
        if name in selected_action_names
    }
    merged_buttons = {
        name: values
        for name, values in _merge_bindings(TIBIA_BUTTON_BINDINGS, button_bindings).items()
        if name in selected_action_names
    }
    return GameProfile.generic(
        name="tibia",
        action_names=selected_actions,
        key_bindings=merged_keys,
        button_bindings=merged_buttons,
        tapped_key_actions=[name for name in TIBIA_TAPPED_KEY_ACTIONS if name in selected_action_names],
        clicked_button_actions=[name for name in TIBIA_CLICKED_BUTTON_ACTIONS if name in selected_action_names],
    )


def tibia_action_names_for(action_names: Iterable[str] | None) -> list[str]:
    if action_names is None:
        return list(TIBIA_ACTIONS)
    return [name for name in action_names]
