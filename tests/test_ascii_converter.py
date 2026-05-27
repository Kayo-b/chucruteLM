from __future__ import annotations

import unittest

import numpy as np

from chucrutelm.ascii import AsciiConverter
from chucrutelm.config import GridSize


class AsciiConverterTest(unittest.TestCase):
    def test_convert_simple_respects_grid_size(self) -> None:
        frame = np.arange(0, 64, dtype=np.uint8).reshape(8, 8)
        converter = AsciiConverter(GridSize(width=4, height=2))
        ascii_text = converter.convert_simple(frame)
        lines = ascii_text.splitlines()
        self.assertEqual(len(lines), 2)
        self.assertTrue(all(len(line) == 4 for line in lines))


if __name__ == "__main__":
    unittest.main()
