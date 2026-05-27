from __future__ import annotations

import json
from pathlib import Path
import random

import torch
from torch.utils.data import Dataset, Subset

from ..actions import ActionSpace
from ..config import GridSize
from ..model.tokenizer import AsciiGridTokenizer
from ..schemas import RecordedFrame


class BehaviorCloningDataset(Dataset):
    def __init__(
        self,
        manifest_path: Path,
        tokenizer: AsciiGridTokenizer,
        action_space: ActionSpace,
        grid_size: GridSize,
        feature_names: list[str] | None = None,
    ) -> None:
        self.tokenizer = tokenizer
        self.action_space = action_space
        self.grid_size = grid_size
        self.records: list[RecordedFrame] = []

        with manifest_path.open("r", encoding="utf-8") as handle:
            for line in handle:
                if not line.strip():
                    continue
                record = RecordedFrame.from_json(line)
                if record.action.action_name is None or record.action.action_name not in action_space:
                    continue
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
