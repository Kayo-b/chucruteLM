from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Protocol

import numpy as np

from ..actions import ActionSpace
from ..config import CaptureRegion
from ..input_names import normalize_button_name, normalize_key_name


class UiExtractor(Protocol):
    def extract(self, frame: np.ndarray) -> Mapping[str, float]:
        """Extract numeric UI values from a frame."""


class NullUiExtractor:
    def extract(self, frame: np.ndarray) -> Mapping[str, float]:
        del frame
        return {}


@dataclass(frozen=True)
class PointerAction:
    action_name: str
    pointer_target: tuple[int, int]
    button: str


def _normalize_binding_sets(
    bindings: Mapping[str, Sequence[Sequence[str]] | Sequence[str]] | None,
    *,
    normalizer: Callable[[object], str],
) -> dict[str, tuple[tuple[str, ...], ...]]:
    if bindings is None:
        return {}

    normalized: dict[str, tuple[tuple[str, ...], ...]] = {}
    for action_name, value in bindings.items():
        entries = tuple(value)
        if not entries:
            normalized[action_name] = ()
            continue
        if isinstance(entries[0], str):
            normalized[action_name] = tuple((normalizer(item),) for item in entries)  # type: ignore[arg-type]
            continue
        normalized[action_name] = tuple(
            tuple(normalizer(item) for item in combo if str(item)) for combo in entries
        )  # type: ignore[arg-type]
    return normalized


@dataclass
class GameProfile:
    name: str
    action_space: ActionSpace
    key_bindings: dict[str, tuple[tuple[str, ...], ...]] = field(default_factory=dict)
    button_bindings: dict[str, tuple[tuple[str, ...], ...]] = field(default_factory=dict)
    held_key_actions: frozenset[str] = field(default_factory=frozenset)
    tapped_key_actions: frozenset[str] = field(default_factory=frozenset)
    clicked_button_actions: frozenset[str] = field(default_factory=frozenset)
    ui_extractor: UiExtractor = field(default_factory=NullUiExtractor)
    pointer_action_resolver: Callable[[str, CaptureRegion], PointerAction | None] | None = None
    pointer_origin_resolver: Callable[[CaptureRegion], tuple[int, int] | None] | None = None

    def extract_numeric_features(self, frame: np.ndarray) -> dict[str, float]:
        return dict(self.ui_extractor.extract(frame))

    def infer_action(self, raw_inputs: Mapping[str, object]) -> str | None:
        pressed_keys = {normalize_key_name(name) for name in raw_inputs.get("pressed_keys", ())}
        pressed_buttons = {normalize_button_name(name) for name in raw_inputs.get("pressed_buttons", ())}
        best_action_name = self._best_matching_action(pressed_keys, pressed_buttons)
        if best_action_name is not None:
            return best_action_name

        tapped_keys = tuple(normalize_key_name(name) for name in raw_inputs.get("tapped_keys", ()))
        tapped_buttons = tuple(normalize_button_name(name) for name in raw_inputs.get("tapped_buttons", ()))
        tapped_action_name = self._most_recent_tapped_action(tapped_keys, tapped_buttons)
        if tapped_action_name is not None:
            return tapped_action_name
        if "noop" in self.action_space:
            return "noop"
        return None

    def bindings_for_action(
        self,
        action_name: str,
    ) -> tuple[tuple[tuple[str, ...], ...], tuple[tuple[str, ...], ...]]:
        if action_name not in self.action_space:
            raise KeyError(f"Unknown action: {action_name}")
        return self.key_bindings.get(action_name, ()), self.button_bindings.get(action_name, ())

    def held_keys_for_action(self, action_name: str) -> tuple[str, ...]:
        keys, _ = self.bindings_for_action(action_name)
        if action_name not in self.held_key_actions:
            return ()
        return keys[0] if keys else ()

    def tapped_keys_for_action(self, action_name: str) -> tuple[str, ...]:
        keys, _ = self.bindings_for_action(action_name)
        if action_name in self.held_key_actions:
            return ()
        if self.tapped_key_actions and action_name not in self.tapped_key_actions:
            return ()
        return keys[0] if keys else ()

    def clicked_buttons_for_action(self, action_name: str) -> tuple[str, ...]:
        _, buttons = self.bindings_for_action(action_name)
        if self.clicked_button_actions and action_name not in self.clicked_button_actions:
            return ()
        return buttons[0] if buttons else ()

    def resolve_pointer_action(
        self,
        action_name: str,
        capture_region: CaptureRegion,
    ) -> PointerAction | None:
        if action_name not in self.action_space:
            raise KeyError(f"Unknown action: {action_name}")
        if self.pointer_action_resolver is None:
            return None
        return self.pointer_action_resolver(action_name, capture_region)

    def default_pointer_position(self, capture_region: CaptureRegion) -> tuple[int, int] | None:
        if self.pointer_origin_resolver is None:
            return None
        return self.pointer_origin_resolver(capture_region)

    def _binding_specificity(
        self,
        action_name: str,
        pressed_keys: set[str],
        pressed_buttons: set[str],
    ) -> int:
        key_candidates = self.key_bindings.get(action_name, ())
        button_candidates = self.button_bindings.get(action_name, ())
        best = 0
        for key_combo in key_candidates:
            if set(key_combo).issubset(pressed_keys):
                best = max(best, len(key_combo))
        for button_combo in button_candidates:
            if set(button_combo).issubset(pressed_buttons):
                best = max(best, len(button_combo))
        return best

    def _best_matching_action(
        self,
        pressed_keys: set[str],
        pressed_buttons: set[str],
    ) -> str | None:
        best_action_name: str | None = None
        best_specificity = 0
        for action_name in self.action_space.names:
            specificity = self._binding_specificity(action_name, pressed_keys, pressed_buttons)
            if specificity > best_specificity:
                best_action_name = action_name
                best_specificity = specificity
        return best_action_name

    def _most_recent_tapped_action(
        self,
        tapped_keys: tuple[str, ...],
        tapped_buttons: tuple[str, ...],
    ) -> str | None:
        single_key_actions = {
            combo[0]: action_name
            for action_name, key_combos in self.key_bindings.items()
            for combo in key_combos
            if len(combo) == 1
        }
        for key_name in reversed(tapped_keys):
            action_name = single_key_actions.get(key_name)
            if action_name is not None and action_name in self.action_space:
                return action_name

        single_button_actions = {
            combo[0]: action_name
            for action_name, button_combos in self.button_bindings.items()
            for combo in button_combos
            if len(combo) == 1
        }
        for button_name in reversed(tapped_buttons):
            action_name = single_button_actions.get(button_name)
            if action_name is not None and action_name in self.action_space:
                return action_name
        return None

    @classmethod
    def generic(
        cls,
        name: str,
        action_names: Sequence[str],
        key_bindings: Mapping[str, Sequence[Sequence[str]] | Sequence[str]] | None = None,
        button_bindings: Mapping[str, Sequence[Sequence[str]] | Sequence[str]] | None = None,
        held_key_actions: Sequence[str] | None = None,
        tapped_key_actions: Sequence[str] | None = None,
        clicked_button_actions: Sequence[str] | None = None,
        pointer_action_resolver: Callable[[str, CaptureRegion], PointerAction | None] | None = None,
        pointer_origin_resolver: Callable[[CaptureRegion], tuple[int, int] | None] | None = None,
    ) -> "GameProfile":
        return cls(
            name=name,
            action_space=ActionSpace.from_names(list(action_names)),
            key_bindings=_normalize_binding_sets(key_bindings, normalizer=normalize_key_name),
            button_bindings=_normalize_binding_sets(button_bindings, normalizer=normalize_button_name),
            held_key_actions=frozenset(held_key_actions or ()),
            tapped_key_actions=frozenset(tapped_key_actions or ()),
            clicked_button_actions=frozenset(clicked_button_actions or ()),
            pointer_action_resolver=pointer_action_resolver,
            pointer_origin_resolver=pointer_origin_resolver,
        )
