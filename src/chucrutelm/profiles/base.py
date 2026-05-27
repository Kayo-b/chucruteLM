from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Protocol

import numpy as np

from ..actions import ActionSpace


class UiExtractor(Protocol):
    def extract(self, frame: np.ndarray) -> Mapping[str, float]:
        """Extract numeric UI values from a frame."""


class NullUiExtractor:
    def extract(self, frame: np.ndarray) -> Mapping[str, float]:
        del frame
        return {}


def _normalize_binding_sets(
    bindings: Mapping[str, Sequence[Sequence[str]] | Sequence[str]] | None,
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
            normalized[action_name] = tuple((str(item),) for item in entries)  # type: ignore[arg-type]
            continue
        normalized[action_name] = tuple(tuple(str(item) for item in combo if str(item)) for combo in entries)  # type: ignore[arg-type]
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

    def extract_numeric_features(self, frame: np.ndarray) -> dict[str, float]:
        return dict(self.ui_extractor.extract(frame))

    def infer_action(self, raw_inputs: Mapping[str, object]) -> str | None:
        pressed_keys = set(raw_inputs.get("pressed_keys", ()))
        pressed_buttons = set(raw_inputs.get("pressed_buttons", ()))
        best_action_name: str | None = None
        best_specificity = 0
        for action_name in self.action_space.names:
            specificity = self._binding_specificity(action_name, pressed_keys, pressed_buttons)
            if specificity > best_specificity:
                best_action_name = action_name
                best_specificity = specificity
        return best_action_name

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
    ) -> "GameProfile":
        return cls(
            name=name,
            action_space=ActionSpace.from_names(list(action_names)),
            key_bindings=_normalize_binding_sets(key_bindings),
            button_bindings=_normalize_binding_sets(button_bindings),
            held_key_actions=frozenset(held_key_actions or ()),
            tapped_key_actions=frozenset(tapped_key_actions or ()),
            clicked_button_actions=frozenset(clicked_button_actions or ()),
        )
