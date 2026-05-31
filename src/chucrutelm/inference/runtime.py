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
        self.tokenizer = AsciiGridTokenizer()
        self.model = AsciiGridPolicyModel(self.model_config)
        state_dict = torch.load(checkpoint_dir / "model.pt", map_location="cpu")
        self.model.load_state_dict(state_dict)
        self.model.eval()

    def predict(self, ascii_text: str) -> tuple[str, torch.Tensor]:
        grid_ids = self.tokenizer.encode_grid(ascii_text, self.model_config.grid_size).unsqueeze(0)
        with torch.no_grad():
            logits = self.model(grid_ids)
        action_index = int(logits.argmax(dim=-1).item())
        return self.action_space.names[action_index], logits.squeeze(0)
