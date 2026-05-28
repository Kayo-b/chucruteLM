from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass

from ..config import CaptureRegion
from .base import GameProfile, PointerAction

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
    "click_tile_north",
    "click_tile_south",
    "click_tile_west",
    "click_tile_east",
    "click_tile_north_west",
    "click_tile_north_east",
    "click_tile_south_west",
    "click_tile_south_east",
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


@dataclass(frozen=True)
class TibiaViewport:
    left: int
    top: int
    width: int
    height: int
    grid_width: int
    grid_height: int
    center_x: int
    center_y: int


@dataclass(frozen=True)
class TibiaViewportConfig:
    left: int = 0
    top: int = 0
    width: int | None = None
    height: int | None = None
    grid_width: int = 15
    grid_height: int = 11
    center_x: int = 7
    center_y: int = 5

    def resolve(self, capture_region: CaptureRegion) -> TibiaViewport:
        width = capture_region.width - self.left if self.width is None else self.width
        height = capture_region.height - self.top if self.height is None else self.height
        if width <= 0 or height <= 0:
            raise ValueError("Tibia viewport dimensions must be positive.")
        return TibiaViewport(
            left=capture_region.left + self.left,
            top=capture_region.top + self.top,
            width=width,
            height=height,
            grid_width=self.grid_width,
            grid_height=self.grid_height,
            center_x=self.center_x,
            center_y=self.center_y,
        )


@dataclass(frozen=True)
class TibiaPointerBinding:
    dx: int
    dy: int
    button: str = "left"


TIBIA_POINTER_BINDINGS: dict[str, TibiaPointerBinding] = {
    "click_tile_north": TibiaPointerBinding(dx=0, dy=-1),
    "click_tile_south": TibiaPointerBinding(dx=0, dy=1),
    "click_tile_west": TibiaPointerBinding(dx=-1, dy=0),
    "click_tile_east": TibiaPointerBinding(dx=1, dy=0),
    "click_tile_north_west": TibiaPointerBinding(dx=-1, dy=-1),
    "click_tile_north_east": TibiaPointerBinding(dx=1, dy=-1),
    "click_tile_south_west": TibiaPointerBinding(dx=-1, dy=1),
    "click_tile_south_east": TibiaPointerBinding(dx=1, dy=1),
}


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


def tile_to_screen(viewport: TibiaViewport, dx: int, dy: int) -> tuple[int, int]:
    tile_w = viewport.width / viewport.grid_width
    tile_h = viewport.height / viewport.grid_height
    x = viewport.left + (viewport.center_x + dx + 0.5) * tile_w
    y = viewport.top + (viewport.center_y + dy + 0.5) * tile_h
    return round(x), round(y)


def viewport_center(viewport: TibiaViewport) -> tuple[int, int]:
    return tile_to_screen(viewport, dx=0, dy=0)


def build_tibia_profile(
    action_names: Sequence[str] | None = None,
    *,
    key_bindings: dict[str, tuple[tuple[str, ...], ...]] | None = None,
    button_bindings: dict[str, tuple[tuple[str, ...], ...]] | None = None,
    viewport_config: TibiaViewportConfig | None = None,
) -> GameProfile:
    selected_actions = tuple(action_names or TIBIA_ACTIONS)
    selected_action_names = frozenset(selected_actions)
    resolved_viewport_config = viewport_config or TibiaViewportConfig()
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

    def resolve_pointer_action(action_name: str, capture_region: CaptureRegion) -> PointerAction | None:
        binding = TIBIA_POINTER_BINDINGS.get(action_name)
        if binding is None:
            return None
        viewport = resolved_viewport_config.resolve(capture_region)
        return PointerAction(
            action_name=action_name,
            pointer_target=tile_to_screen(viewport, binding.dx, binding.dy),
            button=binding.button,
        )

    def resolve_pointer_origin(capture_region: CaptureRegion) -> tuple[int, int]:
        viewport = resolved_viewport_config.resolve(capture_region)
        return viewport_center(viewport)

    return GameProfile.generic(
        name="tibia",
        action_names=selected_actions,
        key_bindings=merged_keys,
        button_bindings=merged_buttons,
        tapped_key_actions=[name for name in TIBIA_TAPPED_KEY_ACTIONS if name in selected_action_names],
        clicked_button_actions=[name for name in TIBIA_CLICKED_BUTTON_ACTIONS if name in selected_action_names],
        pointer_action_resolver=resolve_pointer_action,
        pointer_origin_resolver=resolve_pointer_origin,
    )


def tibia_action_names_for(action_names: Iterable[str] | None) -> list[str]:
    if action_names is None:
        return list(TIBIA_ACTIONS)
    return [name for name in action_names]
