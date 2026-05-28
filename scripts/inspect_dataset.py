#!/usr/bin/env python3

from __future__ import annotations

import argparse
from pathlib import Path

from chucrutelm.profiles import build_profile, default_action_names
from chucrutelm.training import recorded_button_presses, summarize_recording


def render_counts(title: str, counts: dict[str, int], width: int) -> None:
    print(title)
    if not counts:
        print("  (none)")
        return
    max_count = max(counts.values())
    for name, count in sorted(counts.items(), key=lambda item: (-item[1], item[0])):
        bar_length = 0 if max_count == 0 else max(1, round(width * (count / max_count)))
        print(f"  {name:<24} {count:>5} {'#' * bar_length}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Inspect a recorded manifest.")
    parser.add_argument("--data", required=True, type=Path)
    parser.add_argument("--profile-name", default="tibia")
    parser.add_argument("--only-button-presses", action="store_true")
    parser.add_argument("--limit", type=int, default=25)
    parser.add_argument("--bar-width", type=int, default=32)
    args = parser.parse_args()

    manifest_path = args.data / "manifest.jsonl"
    metadata_path = args.data / "metadata.json"
    profile = build_profile(args.profile_name, action_names=default_action_names(args.profile_name))
    summary = summarize_recording(manifest_path, profile=profile)

    print(f"Samples: {summary.samples}")
    print(f"Feature names: {list(summary.feature_names)}")
    render_counts("Resolved action distribution:", summary.action_counts, args.bar_width)
    print()
    render_counts("Pressed button totals:", summary.pressed_button_counts, args.bar_width)
    print()
    render_counts("Tapped button totals:", summary.tapped_button_counts, args.bar_width)
    if summary.button_action_counts:
        print()
        render_counts("Button-triggered action totals:", summary.button_action_counts, args.bar_width)
    if args.only_button_presses:
        rows = recorded_button_presses(manifest_path, profile=profile)
        print()
        print("Button press frames:")
        for row in rows[: args.limit]:
            pressed = ",".join(row.pressed_buttons) or "-"
            tapped = ",".join(row.tapped_buttons) or "-"
            action_name = row.action_name or "unlabeled"
            print(
                f"  #{row.frame_index:04d} t={row.timestamp:.3f} "
                f"action={action_name:<20} pressed={pressed:<12} tapped={tapped}"
            )
        remaining = len(rows) - min(len(rows), args.limit)
        if remaining > 0:
            print(f"  ... {remaining} more button press frames")
    if metadata_path.exists():
        print("\nMetadata:")
        print(metadata_path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    main()
