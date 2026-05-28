from __future__ import annotations

from pathlib import Path
import random
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass

import torch
from torch.utils.data import Dataset, Subset

from ..actions import ActionSpace
from ..config import GridSize
from ..model.tokenizer import AsciiGridTokenizer
from ..profiles import GameProfile
from ..schemas import RecordedFrame


@dataclass(frozen=True)
class RecordedButtonPress:
    frame_index: int
    timestamp: float
    action_name: str | None
    pressed_buttons: tuple[str, ...]
    tapped_buttons: tuple[str, ...]


@dataclass(frozen=True)
class RecordingSummary:
    samples: int
    feature_names: tuple[str, ...]
    action_counts: dict[str, int]
    pressed_button_counts: dict[str, int]
    tapped_button_counts: dict[str, int]
    button_action_counts: dict[str, int]


def _raw_inputs_for_inference(record: RecordedFrame) -> dict[str, object]:
    raw_inputs = dict(record.observation.raw_inputs)
    raw_inputs.setdefault("pressed_keys", record.action.pressed_keys)
    raw_inputs.setdefault("pressed_buttons", record.action.pressed_buttons)
    raw_inputs.setdefault("tapped_keys", record.action.tapped_keys)
    raw_inputs.setdefault("tapped_buttons", record.action.tapped_buttons)
    return raw_inputs


def resolved_action_name(
    record: RecordedFrame,
    *,
    profile: GameProfile | None = None,
) -> str | None:
    inferred_action = profile.infer_action(_raw_inputs_for_inference(record)) if profile is not None else None
    if inferred_action not in (None, "noop"):
        return inferred_action
    if record.action.action_name is not None:
        return record.action.action_name
    return inferred_action


def summarize_recording(
    manifest_path: Path,
    *,
    profile: GameProfile | None = None,
) -> RecordingSummary:
    action_counts: Counter[str] = Counter()
    pressed_button_counts: Counter[str] = Counter()
    tapped_button_counts: Counter[str] = Counter()
    button_action_counts: Counter[str] = Counter()
    feature_names: set[str] = set()
    samples = 0

    with manifest_path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            record = RecordedFrame.from_json(line)
            action_name = resolved_action_name(record, profile=profile) or "unlabeled"
            action_counts[action_name] += 1
            pressed_button_counts.update(record.action.pressed_buttons)
            tapped_button_counts.update(record.action.tapped_buttons)
            if record.action.pressed_buttons or record.action.tapped_buttons:
                button_action_counts[action_name] += 1
            feature_names.update(record.observation.numeric_features.keys())
            samples += 1

    return RecordingSummary(
        samples=samples,
        feature_names=tuple(sorted(feature_names)),
        action_counts=dict(action_counts),
        pressed_button_counts=dict(pressed_button_counts),
        tapped_button_counts=dict(tapped_button_counts),
        button_action_counts=dict(button_action_counts),
    )


def recorded_button_presses(
    manifest_path: Path,
    *,
    profile: GameProfile | None = None,
) -> list[RecordedButtonPress]:
    rows: list[RecordedButtonPress] = []
    with manifest_path.open("r", encoding="utf-8") as handle:
        for frame_index, line in enumerate(handle):
            if not line.strip():
                continue
            record = RecordedFrame.from_json(line)
            if not record.action.pressed_buttons and not record.action.tapped_buttons:
                continue
            rows.append(
                RecordedButtonPress(
                    frame_index=frame_index,
                    timestamp=record.observation.timestamp,
                    action_name=resolved_action_name(record, profile=profile),
                    pressed_buttons=record.action.pressed_buttons,
                    tapped_buttons=record.action.tapped_buttons,
                )
            )
    return rows


def recorded_action_names(
    manifest_path: Path,
    *,
    preferred_order: Sequence[str] | None = None,
    profile: GameProfile | None = None,
) -> list[str]:
    seen_actions: set[str] = set()
    with manifest_path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            record = RecordedFrame.from_json(line)
            action_name = resolved_action_name(record, profile=profile)
            if action_name is not None:
                seen_actions.add(str(action_name))
    if preferred_order is None:
        return sorted(seen_actions)

    ordered = [action_name for action_name in preferred_order if action_name in seen_actions]
    extras = sorted(action_name for action_name in seen_actions if action_name not in preferred_order)
    return ordered + extras


class BehaviorCloningDataset(Dataset):
    def __init__(
        self,
        manifest_path: Path,
        tokenizer: AsciiGridTokenizer,
        action_space: ActionSpace,
        grid_size: GridSize,
        feature_names: list[str] | None = None,
        profile: GameProfile | None = None,
    ) -> None:
        self.tokenizer = tokenizer
        self.action_space = action_space
        self.grid_size = grid_size
        self.profile = profile
        self.records: list[RecordedFrame] = []

        with manifest_path.open("r", encoding="utf-8") as handle:
            for line in handle:
                if not line.strip():
                    continue
                record = RecordedFrame.from_json(line)
                action_name = resolved_action_name(record, profile=self.profile)
                if action_name is None or action_name not in action_space:
                    continue
                record.action.action_name = action_name
                self.records.append(record)

        if not self.records:
            raise ValueError("No labeled frames were found in the manifest.")

        if feature_names is None:
            feature_keys = set()
            for record in self.records:
                feature_keys.update(record.observation.numeric_features.keys())
            self.feature_names = sorted(feature_keys)
        else:
            self.feature_names = list(feature_names)

    def __len__(self) -> int:
        return len(self.records)

    def __getitem__(self, index: int) -> dict[str, torch.Tensor]:
        record = self.records[index]
        grid_ids = self.tokenizer.encode_grid(record.observation.ascii_text, self.grid_size)
        numeric_values = [
            float(record.observation.numeric_features.get(name, 0.0))
            for name in self.feature_names
        ]
        return {
            "grid_ids": grid_ids,
            "numeric_features": torch.tensor(numeric_values, dtype=torch.float32),
            "label": torch.tensor(self.action_space.index(record.action.action_name), dtype=torch.long),
        }

    def action_distribution(self) -> dict[str, int]:
        counts = {name: 0 for name in self.action_space.names}
        for record in self.records:
            counts[record.action.action_name] += 1
        return counts


def split_dataset(
    dataset: BehaviorCloningDataset,
    eval_ratio: float,
    seed: int,
) -> tuple[Subset[BehaviorCloningDataset], Subset[BehaviorCloningDataset]]:
    if not 0.0 < eval_ratio < 1.0:
        raise ValueError("eval_ratio must be between 0 and 1.")
    indices = list(range(len(dataset)))
    rng = random.Random(seed)
    rng.shuffle(indices)
    eval_size = max(1, int(len(indices) * eval_ratio))
    eval_indices = indices[:eval_size]
    train_indices = indices[eval_size:]
    if not train_indices:
        raise ValueError("Training split is empty.")
    return Subset(dataset, train_indices), Subset(dataset, eval_indices)
