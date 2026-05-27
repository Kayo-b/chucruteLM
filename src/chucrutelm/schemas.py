from __future__ import annotations

from dataclasses import asdict, dataclass
import json


@dataclass
class ActionEvent:
    action_name: str | None
    source: str
    pressed_keys: tuple[str, ...]
    pressed_buttons: tuple[str, ...]


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
        observation = Observation(**payload["observation"])
        action = ActionEvent(**payload["action"])
        return cls(observation=observation, action=action)
