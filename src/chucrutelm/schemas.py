from __future__ import annotations

from dataclasses import asdict, dataclass
import json

from .input_names import normalize_button_names, normalize_key_names


@dataclass
class ActionEvent:
    action_name: str | None
    source: str
    pressed_keys: tuple[str, ...]
    pressed_buttons: tuple[str, ...]
    tapped_keys: tuple[str, ...] = ()
    tapped_buttons: tuple[str, ...] = ()


@dataclass
class Observation:
    timestamp: float
    grid_width: int
    grid_height: int
    ascii_text: str
    numeric_features: dict[str, float]
    raw_inputs: dict[str, object]
    frame_path: str | None = None


@dataclass
class RecordedFrame:
    observation: Observation
    action: ActionEvent

    def to_json(self) -> str:
        return json.dumps(asdict(self), sort_keys=True)

    @classmethod
    def from_json(cls, line: str) -> "RecordedFrame":
        payload = json.loads(line)
        raw_inputs = dict(payload["observation"]["raw_inputs"])
        raw_inputs["pressed_keys"] = normalize_key_names(raw_inputs.get("pressed_keys", ()))
        raw_inputs["pressed_buttons"] = normalize_button_names(raw_inputs.get("pressed_buttons", ()))
        raw_inputs["tapped_keys"] = normalize_key_names(raw_inputs.get("tapped_keys", ()))
        raw_inputs["tapped_buttons"] = normalize_button_names(raw_inputs.get("tapped_buttons", ()))
        observation = Observation(**payload["observation"])
        observation.raw_inputs = raw_inputs
        action_payload = dict(payload["action"])
        action_payload.setdefault("source", "keyboard_mouse")
        action_payload["pressed_keys"] = normalize_key_names(action_payload.get("pressed_keys", ()))
        action_payload["pressed_buttons"] = normalize_button_names(action_payload.get("pressed_buttons", ()))
        action_payload.setdefault("tapped_keys", ())
        action_payload.setdefault("tapped_buttons", ())
        action_payload["tapped_keys"] = normalize_key_names(action_payload["tapped_keys"])
        action_payload["tapped_buttons"] = normalize_button_names(action_payload["tapped_buttons"])
        action = ActionEvent(**action_payload)
        return cls(observation=observation, action=action)
