from __future__ import annotations

import torch
from torch import nn

from ..config import ModelConfig


class ResidualConvBlock(nn.Module):
    def __init__(self, in_channels: int, out_channels: int) -> None:
        super().__init__()
        self.conv1 = nn.Conv2d(in_channels, out_channels, kernel_size=3, padding=1, bias=False)
        self.norm1 = nn.GroupNorm(num_groups=8, num_channels=out_channels)
        self.conv2 = nn.Conv2d(out_channels, out_channels, kernel_size=3, padding=1, bias=False)
        self.norm2 = nn.GroupNorm(num_groups=8, num_channels=out_channels)
        self.activation = nn.GELU()
        self.shortcut = (
            nn.Identity()
            if in_channels == out_channels
            else nn.Conv2d(in_channels, out_channels, kernel_size=1, bias=False)
        )
        self.pool = nn.AvgPool2d(kernel_size=2, stride=2)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        residual = self.shortcut(x)
        x = self.conv1(x)
        x = self.norm1(x)
        x = self.activation(x)
        x = self.conv2(x)
        x = self.norm2(x)
        x = self.activation(x + residual)
        return self.pool(x)


class AsciiGridPolicyModel(nn.Module):
    def __init__(self, config: ModelConfig) -> None:
        super().__init__()
        self.config = config
        self.embedding = nn.Embedding(config.vocab_size, config.embedding_dim)

        channels = (config.embedding_dim,) + config.channels
        self.conv_tower = nn.Sequential(
            *[
                ResidualConvBlock(channels[index], channels[index + 1])
                for index in range(len(channels) - 1)
            ]
        )
        self.pool = nn.AdaptiveAvgPool2d(1)

        self.classifier = nn.Sequential(
            nn.Linear(config.channels[-1], config.classifier_hidden_dim),
            nn.GELU(),
            nn.Dropout(config.dropout),
            nn.Linear(config.classifier_hidden_dim, config.num_actions),
        )

    def forward(self, grid_ids: torch.Tensor) -> torch.Tensor:
        if grid_ids.dim() != 3:
            raise ValueError("grid_ids must have shape [batch, height, width].")
        x = self.embedding(grid_ids)
        x = x.permute(0, 3, 1, 2)
        x = self.conv_tower(x)
        x = self.pool(x).flatten(start_dim=1)
        return self.classifier(x)

    def parameter_count(self) -> int:
        return sum(parameter.numel() for parameter in self.parameters())
