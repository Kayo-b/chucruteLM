#!/usr/bin/env python3

from __future__ import annotations

import argparse
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from chucrutelm.capture.linux import resolve_evdev_device


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Resolve the evdev paths used by the recording wrapper."
    )
    parser.add_argument("--keyboard-name", default="Corne Keyboard")
    parser.add_argument("--mouse-name", default="Logitech G502 HERO Gaming Mouse")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    for path in (
        resolve_evdev_device(args.keyboard_name, kind="keyboard"),
        resolve_evdev_device(args.mouse_name, kind="mouse"),
    ):
        print(path)


if __name__ == "__main__":
    main()
