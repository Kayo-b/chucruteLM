from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import TYPE_CHECKING

import torch
from torch import nn
from torch.utils.data import DataLoader, Dataset

from ..actions import ActionSpace
from ..config import ModelConfig, TrainingConfig
from ..model.policy import AsciiGridPolicyModel

if TYPE_CHECKING:
    from .dataset import BehaviorCloningDataset

logger = logging.getLogger(__name__)


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
        class_weights = self._class_weights(train_dataset)
        optimizer = torch.optim.AdamW(
            self.model.parameters(),
            lr=self.config.learning_rate,
            weight_decay=self.config.weight_decay,
        )
        scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(
            optimizer,
            T_max=self.config.epochs,
        )
        criterion = nn.CrossEntropyLoss(weight=class_weights)
        best_accuracy = 0.0
        self.config.output_dir.mkdir(parents=True, exist_ok=True)

        for epoch in range(1, self.config.epochs + 1):
            self.model.train()
            total_loss = 0.0
            num_batches = 0
            for batch in train_loader:
                optimizer.zero_grad(set_to_none=True)
                logits = self.model(batch["grid_ids"].to(self.device))
                loss = criterion(logits, batch["label"].to(self.device))
                loss.backward()
                optimizer.step()
                total_loss += loss.item()
                num_batches += 1
            scheduler.step()
            avg_loss = total_loss / max(num_batches, 1)
            accuracy = self.evaluate(eval_loader)
            logger.info(
                "Epoch %d/%d | loss: %.4f | eval acc: %.2f%%",
                epoch,
                self.config.epochs,
                avg_loss,
                accuracy * 100,
            )
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
                logits = self.model(batch["grid_ids"].to(self.device))
                predictions = logits.argmax(dim=-1)
                labels = batch["label"].to(self.device)
                correct += int((predictions == labels).sum().item())
                total += int(labels.numel())
        return correct / total if total else 0.0

    def save_metadata(self, model_config: ModelConfig) -> None:
        payload = {
            "model_config": model_config.to_dict(),
            "actions": list(self.action_space.names),
        }
        metadata_path = self.config.output_dir / "metadata.json"
        metadata_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")

    def _class_weights(self, train_dataset: Dataset) -> torch.Tensor:
        base = getattr(train_dataset, "dataset", train_dataset)
        indices = getattr(train_dataset, "indices", None)
        counts = base.label_counts(list(indices) if indices is not None else None)
        num_classes = counts.shape[0]
        weights = counts.sum() / (num_classes * counts.clamp(min=1.0))
        return weights.to(self.device)
