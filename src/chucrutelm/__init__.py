"""Tibia-first screen-only behavioral cloning package."""

from .actions import ActionSpace, DiscreteAction
from .config import CaptureRegion, GridSize, ModelConfig, RecordingConfig, TrainingConfig

__all__ = [
    "ActionSpace",
    "CaptureRegion",
    "DiscreteAction",
    "GridSize",
    "ModelConfig",
    "RecordingConfig",
    "TrainingConfig",
]
