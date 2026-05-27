from __future__ import annotations

import json
from pathlib import Path

import torch

from ..actions import ActionSpace
from ..config import ModelConfig
from ..model.policy import AsciiGridPolicyModel
from ..model.tokenizer import AsciiGridTokenizer


class PolicyRuntime:
    def __init__(self, checkpoint_dir: Path) -> None:
        metadata = json.loads((checkpoint_dir / "metadata.json").read_text(encoding="utf-8"))
        self.model_config = ModelConfig.from_dict(metadata["model_config"])
        self.action_space = ActionSpace.from_names(list(metadata["actions"]))
        self.feature_names = list(metadata["feature_names"])
        self.tokenizer = AsciiGridTokenizer()
        self.model = AsciiGridPolicyModel(self.model_config)
        state_dict = torch.load(checkpoint_dir / "model.pt", map_location="cpu")
        self.model.load_state_dict(state_dict)
        self.model.eval()

    def predict(
        self,
        ascii_text: str,
        numeric_features: dict[str, float] | None = None,
    ) -> tuple[str, torch.Tensor]:
        feature_vector = [
            float((numeric_features or {}).get(name, 0.0))
            for name in self.feature_names
        ]
        grid_ids = self.tokenizer.encode_grid(ascii_text, self.model_config.grid_size).unsqueeze(0)
        numeric_tensor = torch.tensor([feature_vector], dtype=torch.float32)
        with torch.no_grad():
            logits = self.model(grid_ids, numeric_tensor)
        action_index = int(logits.argmax(dim=-1).item())
        return self.action_space.names[action_index], logits.squeeze(0)
