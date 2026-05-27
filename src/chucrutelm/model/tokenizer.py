from __future__ import annotations

import torch

from ..ascii.charset import DEFAULT_CHARSET
from ..config import GridSize


class AsciiGridTokenizer:
    def __init__(self, charset: str = DEFAULT_CHARSET) -> None:
        self.charset = charset
        self.char_to_id = {char: idx for idx, char in enumerate(charset)}
        self.unknown_id = self.char_to_id.get(" ", 0)

    def encode_grid(self, ascii_text: str, grid_size: GridSize) -> torch.Tensor:
        lines = ascii_text.splitlines()
        normalized_lines: list[str] = []
        for row_index in range(grid_size.height):
            line = lines[row_index] if row_index < len(lines) else ""
            normalized_lines.append(line[: grid_size.width].ljust(grid_size.width))
        rows = [
            [self.char_to_id.get(char, self.unknown_id) for char in line]
            for line in normalized_lines
        ]
        return torch.tensor(rows, dtype=torch.long)
