from __future__ import annotations

import numpy as np
from PIL import Image

from ..config import GridSize
from .charset import DEFAULT_CHARSET


class AsciiConverter:
    def __init__(self, grid_size: GridSize, charset: str = DEFAULT_CHARSET) -> None:
        if not charset:
            raise ValueError("charset must not be empty")
        self.grid_size = grid_size
        self.charset = charset

    def convert_lines(self, frame: np.ndarray) -> list[str]:
        gray = self._to_grayscale(frame)
        resized = Image.fromarray(gray).resize(
            (self.grid_size.width, self.grid_size.height),
            Image.Resampling.BILINEAR,
        )
        pixel_array = np.asarray(resized, dtype=np.uint8)
        scale = len(self.charset) - 1
        indices = np.rint((pixel_array.astype(np.float32) / 255.0) * scale).astype(np.int32)
        return ["".join(self.charset[index] for index in row) for row in indices]

    def convert_simple(self, frame: np.ndarray) -> str:
        return "\n".join(self.convert_lines(frame))

    @staticmethod
    def _to_grayscale(frame: np.ndarray) -> np.ndarray:
        if frame.ndim == 2:
            return frame.astype(np.uint8)
        if frame.ndim != 3 or frame.shape[2] < 3:
            raise ValueError("frame must be grayscale or RGB-like")
        rgb = frame[:, :, :3].astype(np.float32)
        gray = np.dot(rgb, np.array([0.299, 0.587, 0.114], dtype=np.float32))
        return np.clip(gray, 0, 255).astype(np.uint8)
