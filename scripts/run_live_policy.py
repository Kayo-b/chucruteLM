#!/usr/bin/env python3

from __future__ import annotations

import argparse
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))


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
    parser = argparse.ArgumentParser(description="Run a trained policy live against a desktop region.")
    parser.add_argument("--checkpoint", required=True, type=Path)
    parser.add_argument("--left", type=int)
    parser.add_argument("--top", type=int)
    parser.add_argument("--width", type=int)
    parser.add_argument("--height", type=int)
    parser.add_argument("--fps", type=float, default=5.0)
    parser.add_argument("--duration", type=float, default=None)
    parser.add_argument("--capture-backend", choices=("auto", "mss", "grim"), default="auto")
    parser.add_argument("--action-backend", choices=("noop", "uinput"), default="noop")
    parser.add_argument("--list-windows", action="store_true")
    parser.add_argument("--window-class")
    parser.add_argument("--window-title")
    parser.add_argument("--profile-name", default="tibia")
    parser.add_argument("--actions")
    parser.add_argument("--key-binding", action="append", default=[])
    parser.add_argument("--button-binding", action="append", default=[])
    parser.add_argument("--key-press-ms", type=float, default=50.0)
    parser.add_argument("--key-repeat-ms", type=float, default=200.0)
    parser.add_argument("--button-press-ms", type=float, default=50.0)
    parser.add_argument("--button-repeat-ms", type=float, default=200.0)
    parser.add_argument("--pointer-repeat-ms", type=float, default=200.0)
    parser.add_argument("--device-name", default="chucrutelm-virtual-input")
    parser.add_argument("--pointer-start-x", type=int)
    parser.add_argument("--pointer-start-y", type=int)
    parser.add_argument("--tibia-viewport-left", type=int, default=0)
    parser.add_argument("--tibia-viewport-top", type=int, default=0)
    parser.add_argument("--tibia-viewport-width", type=int)
    parser.add_argument("--tibia-viewport-height", type=int)
    parser.add_argument("--tibia-grid-width", type=int, default=15)
    parser.add_argument("--tibia-grid-height", type=int, default=11)
    parser.add_argument("--tibia-center-x", type=int, default=7)
    parser.add_argument("--tibia-center-y", type=int, default=5)
    parser.add_argument("--print-actions", action="store_true")
    return parser


def main() -> None:
    from chucrutelm.ascii import AsciiConverter
    from chucrutelm.capture import ScreenCaptureBackend, list_open_windows, resolve_capture_region
    from chucrutelm.control import ActionExecutor, NoopActionBackend, UinputActionBackend
    from chucrutelm.inference import LivePolicyConfig, LivePolicyRunner, PolicyRuntime
    from chucrutelm.profiles import TibiaViewportConfig, build_profile, default_window_selectors

    args = build_parser().parse_args()
    if args.list_windows:
        for window in list_open_windows():
            print(
                f"{window.class_name}\t{window.title}\t"
                f"{window.region.left},{window.region.top} {window.region.width}x{window.region.height}"
            )
        return
    runtime = PolicyRuntime(args.checkpoint)
    action_names = parse_action_names(args.actions) or list(runtime.action_space.names)
    window_class = args.window_class
    window_title = args.window_title
    if all(value is None for value in (args.left, args.top, args.width, args.height, window_class, window_title)):
        window_class, window_title = default_window_selectors(args.profile_name)
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
    if (args.pointer_start_x is None) != (args.pointer_start_y is None):
        raise SystemExit("--pointer-start-x and --pointer-start-y must be provided together.")
    profile = build_profile(
        args.profile_name,
        action_names=action_names,
        key_bindings=parse_bindings(args.key_binding),
        button_bindings=parse_bindings(args.button_binding),
        tibia_viewport=TibiaViewportConfig(
            left=args.tibia_viewport_left,
            top=args.tibia_viewport_top,
            width=args.tibia_viewport_width,
            height=args.tibia_viewport_height,
            grid_width=args.tibia_grid_width,
            grid_height=args.tibia_grid_height,
            center_x=args.tibia_center_x,
            center_y=args.tibia_center_y,
        )
        if args.profile_name == "tibia"
        else None,
    )
    pointer_start = (
        (args.pointer_start_x, args.pointer_start_y)
        if args.pointer_start_x is not None and args.pointer_start_y is not None
        else profile.default_pointer_position(region)
    )

    if args.action_backend == "uinput":
        backend = UinputActionBackend.from_profile(profile, device_name=args.device_name)
    else:
        backend = NoopActionBackend()

    runner = LivePolicyRunner(
        runtime=runtime,
        capture_backend=ScreenCaptureBackend(
            region,
            backend=args.capture_backend,
        ),
        profile=profile,
        ascii_converter=AsciiConverter(runtime.model_config.grid_size),
        action_executor=ActionExecutor(
            profile=profile,
            backend=backend,
            key_press_s=args.key_press_ms / 1000.0,
            key_repeat_s=args.key_repeat_ms / 1000.0,
            button_press_s=args.button_press_ms / 1000.0,
            button_repeat_s=args.button_repeat_ms / 1000.0,
            pointer_repeat_s=args.pointer_repeat_ms / 1000.0,
            initial_pointer_position=pointer_start,
        ),
        config=LivePolicyConfig(
            fps=args.fps,
            duration_s=args.duration,
            print_actions=args.print_actions,
        ),
    )
    total = runner.run()
    print(f"Ran {total} live inference steps from {args.checkpoint}")


if __name__ == "__main__":
    main()
