from __future__ import annotations

import json
from pathlib import Path

import torch
from torch import nn
from torch.utils.data import DataLoader, Dataset

from ..actions import ActionSpace
from ..config import ModelConfig, TrainingConfig
from ..model.policy import AsciiGridPolicyModel


class BehaviorCloningTrainer:
    def __init__(
        self,
        model: AsciiGridPolicyModel,
        action_space: ActionSpace,
        config: TrainingConfig,
    ) -> None:
        self.model = model
        self.action_space = action_space
        self.config = config
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.model.to(self.device)

    def train(self, train_dataset: Dataset, eval_dataset: Dataset) -> float:
        train_loader = DataLoader(train_dataset, batch_size=self.config.batch_size, shuffle=True)
        eval_loader = DataLoader(eval_dataset, batch_size=self.config.batch_size, shuffle=False)
        optimizer = torch.optim.AdamW(
            self.model.parameters(),
            lr=self.config.learning_rate,
            weight_decay=self.config.weight_decay,
        )
        criterion = nn.CrossEntropyLoss()
        best_accuracy = 0.0
        self.config.output_dir.mkdir(parents=True, exist_ok=True)

        for epoch in range(1, self.config.epochs + 1):
            self.model.train()
            for batch in train_loader:
                optimizer.zero_grad(set_to_none=True)
                logits = self.model(
                    batch["grid_ids"].to(self.device),
                    batch["numeric_features"].to(self.device),
                )
                loss = criterion(logits, batch["label"].to(self.device))
                loss.backward()
                optimizer.step()
            accuracy = self.evaluate(eval_loader)
            if accuracy >= best_accuracy:
                best_accuracy = accuracy
                torch.save(self.model.state_dict(), self.config.output_dir / "model.pt")
        return best_accuracy

    def evaluate(self, dataloader: DataLoader) -> float:
        self.model.eval()
        total = 0
        correct = 0
        with torch.no_grad():
            for batch in dataloader:
                logits = self.model(
                    batch["grid_ids"].to(self.device),
                    batch["numeric_features"].to(self.device),
                )
                predictions = logits.argmax(dim=-1)
                labels = batch["label"].to(self.device)
                correct += int((predictions == labels).sum().item())
                total += int(labels.numel())
        return correct / total if total else 0.0

    def save_metadata(
        self,
        model_config: ModelConfig,
        feature_names: list[str],
    ) -> None:
        payload = {
            "model_config": model_config.to_dict(),
            "actions": list(self.action_space.names),
            "feature_names": feature_names,
        }
        metadata_path = self.config.output_dir / "metadata.json"
        metadata_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
