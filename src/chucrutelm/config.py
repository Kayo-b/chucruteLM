from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class GridSize:
    width: int = 80
    height: int = 60


@dataclass(frozen=True)
class CaptureRegion:
    left: int
    top: int
    width: int
    height: int

    def as_mss_region(self) -> dict[str, int]:
        return {
            "left": self.left,
            "top": self.top,
            "width": self.width,
            "height": self.height,
        }


@dataclass
class RecordingConfig:
    output_dir: Path
    region: CaptureRegion
    grid_size: GridSize = field(default_factory=GridSize)
    fps: float = 5.0
    duration_s: float | None = None
    max_frames: int | None = None
    save_frames: bool = False


@dataclass
class ModelConfig:
    grid_size: GridSize = field(default_factory=GridSize)
    vocab_size: int = 128
    embedding_dim: int = 48
    channels: tuple[int, ...] = (96, 128, 192, 192)
    numeric_feature_dim: int = 0
    numeric_hidden_dim: int = 64
    classifier_hidden_dim: int = 256
    num_actions: int = 8
    dropout: float = 0.1

    def to_dict(self) -> dict[str, object]:
        payload = asdict(self)
        payload["grid_size"] = asdict(self.grid_size)
        return payload

    @classmethod
    def from_dict(cls, payload: dict[str, object]) -> "ModelConfig":
        grid_payload = payload.get("grid_size", {})
        grid_size = GridSize(**grid_payload)
        return cls(
            grid_size=grid_size,
            vocab_size=int(payload["vocab_size"]),
            embedding_dim=int(payload["embedding_dim"]),
            channels=tuple(int(value) for value in payload["channels"]),
            numeric_feature_dim=int(payload["numeric_feature_dim"]),
            numeric_hidden_dim=int(payload["numeric_hidden_dim"]),
            classifier_hidden_dim=int(payload["classifier_hidden_dim"]),
            num_actions=int(payload["num_actions"]),
            dropout=float(payload["dropout"]),
        )


@dataclass
class TrainingConfig:
    data_path: Path
    output_dir: Path
    batch_size: int = 32
    epochs: int = 5
    learning_rate: float = 3e-4
    weight_decay: float = 0.01
    eval_split: float = 0.1
    seed: int = 42
