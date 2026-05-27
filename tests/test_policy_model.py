from __future__ import annotations

import unittest

import torch

from chucrutelm.config import GridSize, ModelConfig
from chucrutelm.model import AsciiGridPolicyModel


class PolicyModelTest(unittest.TestCase):
    def test_forward_shape(self) -> None:
        model = AsciiGridPolicyModel(
            ModelConfig(
                grid_size=GridSize(width=8, height=8),
                vocab_size=96,
                channels=(32, 48),
                numeric_feature_dim=3,
                numeric_hidden_dim=8,
                classifier_hidden_dim=16,
                num_actions=5,
            )
        )
        grid_ids = torch.randint(0, 96, (2, 8, 8))
        numeric_features = torch.randn(2, 3)
        logits = model(grid_ids, numeric_features)
        self.assertEqual(tuple(logits.shape), (2, 5))


if __name__ == "__main__":
    unittest.main()
