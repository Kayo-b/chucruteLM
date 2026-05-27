#!/usr/bin/env python3

from __future__ import annotations

import argparse
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from chucrutelm.capture.linux import describe_evdev_devices


def parse_bindings(items: list[str]) -> dict[str, tuple[tuple[str, ...], ...]]:
    bindings: dict[str, tuple[tuple[str, ...], ...]] = {}
    for item in items:
        action_name, values = item.split("=", maxsplit=1)
        bindings[action_name] = tuple(
            tuple(part.strip() for part in value.split("+") if part.strip())
            for value in values.split("|")
            if value.strip()
        )
    return bindings


def parse_action_names(value: str | None) -> list[str] | None:
    if value is None:
        return None
    return [name.strip() for name in value.split(",") if name.strip()]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Record synchronized desktop gameplay data.")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--left", type=int)
    parser.add_argument("--top", type=int)
    parser.add_argument("--width", type=int)
    parser.add_argument("--height", type=int)
    parser.add_argument("--grid-width", type=int, default=80)
    parser.add_argument("--grid-height", type=int, default=60)
    parser.add_argument("--fps", type=float, default=5.0)
    parser.add_argument("--duration", type=float, default=None)
    parser.add_argument("--max-frames", type=int, default=None)
    parser.add_argument("--save-frames", action="store_true")
    parser.add_argument("--capture-backend", choices=("auto", "mss", "grim"), default="auto")
    parser.add_argument("--input-backend", choices=("auto", "pynput", "evdev"), default="auto")
    parser.add_argument("--input-device", action="append", default=[])
    parser.add_argument("--list-input-devices", action="store_true")
    parser.add_argument("--list-windows", action="store_true")
    parser.add_argument("--window-class")
    parser.add_argument("--window-title")
    parser.add_argument("--profile-name", default="tibia")
    parser.add_argument("--actions")
    parser.add_argument("--key-binding", action="append", default=[])
    parser.add_argument("--button-binding", action="append", default=[])
    return parser


def main() -> None:
    args = build_parser().parse_args()
    if args.list_input_devices:
        for entry in describe_evdev_devices():
            if "error" in entry:
                print(f"{entry['path']}\terror={entry['error']}")
                continue
            kinds = [
                label
                for label, enabled in (
                    ("keyboard", entry.get("keyboard")),
                    ("mouse", entry.get("mouse")),
                    ("pointer", entry.get("pointer")),
                )
                if enabled
            ]
            print(f"{entry['path']}\t{entry.get('name', 'unknown')}\t{','.join(kinds) or 'other'}")
        return
    if args.list_windows:
        from chucrutelm.capture import list_open_windows

        for window in list_open_windows():
            print(
                f"{window.class_name}\t{window.title}\t"
                f"{window.region.left},{window.region.top} {window.region.width}x{window.region.height}"
            )
        return
    from chucrutelm.ascii import AsciiConverter
    from chucrutelm.capture import LinuxInputObserver, ScreenCaptureBackend, resolve_capture_region
    from chucrutelm.config import GridSize, RecordingConfig
    from chucrutelm.data import JsonlRecorder, SynchronizedRecorder
    from chucrutelm.profiles import build_profile, default_action_names, default_window_selectors

    action_names = parse_action_names(args.actions)
    if action_names is None:
        action_names = default_action_names(args.profile_name)
    window_class = args.window_class
    window_title = args.window_title
    if all(value is None for value in (args.left, args.top, args.width, args.height, window_class, window_title)):
        window_class, window_title = default_window_selectors(args.profile_name)
    if args.output is None:
        raise SystemExit("Missing required arguments: --output")
    try:
        region = resolve_capture_region(
            left=args.left,
            top=args.top,
            width=args.width,
            height=args.height,
            window_class=window_class,
            window_title=window_title,
        )
    except RuntimeError as exc:
        raise SystemExit(str(exc)) from exc
    profile = build_profile(
        args.profile_name,
        action_names=action_names,
        key_bindings=parse_bindings(args.key_binding),
        button_bindings=parse_bindings(args.button_binding),
    )
    config = RecordingConfig(
        output_dir=args.output,
        region=region,
        grid_size=GridSize(args.grid_width, args.grid_height),
        fps=args.fps,
        duration_s=args.duration,
        max_frames=args.max_frames,
        save_frames=args.save_frames,
    )
    recorder = SynchronizedRecorder(
        config=config,
        capture_backend=ScreenCaptureBackend(config.region, backend=args.capture_backend),
        input_observer=LinuxInputObserver(
            backend=args.input_backend,
            device_paths=args.input_device,
        ),
        profile=profile,
        ascii_converter=AsciiConverter(config.grid_size),
        recorder=JsonlRecorder(config.output_dir, save_frames=config.save_frames),
    )
    total = recorder.record()
    print(f"Recorded {total} synchronized frames to {config.output_dir}")


if __name__ == "__main__":
    main()
